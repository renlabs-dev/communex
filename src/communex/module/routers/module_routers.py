import json
import re
from abc import abstractmethod
from datetime import datetime, timezone
from functools import partial
from typing import Any, Protocol, Sequence

import starlette.datastructures
from communex._common import get_node_url
from communex.module import _signer as signer
from communex.module._rate_limiters._stake_limiter import StakeLimiter
from communex.module._rate_limiters.limiters import (
    IpLimiterParams,
    StakeLimiterParams,
)
from communex.module._util import (
    json_error,
    log,
    log_reffusal,
    make_client,
    try_ss58_decode,
)
from communex.types import Ss58Address
from communex.util.memo import TTLDict
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from keylimiter import TokenBucketLimiter
from substrateinterface import Keypair

HEX_PATTERN = re.compile(r"^[0-9a-fA-F]+$")


def is_hex_string(string: str):
    return bool(HEX_PATTERN.match(string))


def parse_hex(hex_str: str) -> bytes:
    if hex_str[0:2] == "0x":
        return bytes.fromhex(hex_str[2:])
    else:
        return bytes.fromhex(hex_str)


class AbstractVerifier(Protocol):
    @abstractmethod
    async def verify(self, request: Request) -> JSONResponse | None:
        """Please dont mutate the request D:"""
        ...


class StakeLimiterVerifier(AbstractVerifier):
    def __init__(
        self,
        subnets_whitelist: list[int] | None,
        params_: StakeLimiterParams | None,
    ):
        self.subnets_whitelist = subnets_whitelist
        self.params_ = params_
        if not self.params_:
            params = StakeLimiterParams()
        else:
            params = self.params_
        self.limiter = StakeLimiter(
            self.subnets_whitelist,
            epoch=params.epoch,
            max_cache_age=params.cache_age,
            get_refill_rate=params.get_refill_per_epoch,
        )

    async def verify(self, request: Request):
        if request.client is None:
            response = JSONResponse(
                status_code=401,
                content={"error": "Address should be present in request"},
            )
            return response

        key = request.headers.get("x-key")
        if not key:
            response = JSONResponse(
                status_code=401,
                content={"error": "Valid X-Key not provided on headers"},
            )
            return response

        is_allowed = await self.limiter.allow(key)

        if not is_allowed:
            response = JSONResponse(
                status_code=429,
                headers={
                    "X-RateLimit-TryAfter": f"{str(await self.limiter.retry_after(key))} seconds"
                },
                content={"error": "Rate limit exceeded"},
            )
            return response
        return None


class ListVerifier(AbstractVerifier):
    def __init__(
        self,
        blacklist: list[Ss58Address] | None,
        whitelist: list[Ss58Address] | None,
        ip_blacklist: list[str] | None,
    ):
        self.blacklist = blacklist
        self.whitelist = whitelist
        self.ip_blacklist = ip_blacklist

    async def verify(self, request: Request) -> JSONResponse | None:
        key = request.headers.get("x-key")
        if not key:
            reason = "Missing header: X-Key"
            log(f"INFO: refusing module request because: {reason}")
            return json_error(400, "Missing header: X-Key")

        ss58 = try_ss58_decode(key)
        if ss58 is None:
            reason = "Caller key could not be decoded into a ss58address"
            log_reffusal(key, reason)
            return json_error(400, reason)
        if request.client is None:
            return json_error(400, "Address should be present in request")
        if self.blacklist and ss58 in self.blacklist:
            return json_error(403, "You are blacklisted")
        if self.ip_blacklist and request.client.host in self.ip_blacklist:
            return json_error(403, "Your IP is blacklisted")
        if self.whitelist and ss58 not in self.whitelist:
            return json_error(403, "You are not whitelisted")
        return None


class IpLimiterVerifier(AbstractVerifier):
    def __init__(
        self,
        params: IpLimiterParams | None,
    ):
        """
        :param limiter: KeyLimiter instance OR None

        If limiter is None, then a default TokenBucketLimiter is used with the following config:
        bucket_size=200, refill_rate=15
        """

        # fallback to default limiter
        if not params:
            params = IpLimiterParams()
        self._limiter = TokenBucketLimiter(
            bucket_size=params.bucket_size, refill_rate=params.refill_rate
        )

    async def verify(self, request: Request):
        assert request.client is not None, "request is invalid"
        assert request.client.host, "request is invalid."

        ip = request.client.host

        is_allowed = self._limiter.allow(ip)

        if not is_allowed:
            response = JSONResponse(
                status_code=429,
                headers={
                    "X-RateLimit-Remaining": str(self._limiter.remaining(ip))
                },
                content={"error": "Rate limit exceeded"},
            )
            return response
        return None


class InputHandlerVerifier(AbstractVerifier):
    def __init__(
        self,
        subnets_whitelist: list[int] | None,
        module_key: Ss58Address,
        request_staleness: int,
        blockchain_cache: TTLDict[str, list[Ss58Address]],
        host_key: Keypair,
        use_testnet: bool,
    ):
        self.subnets_whitelist = subnets_whitelist
        self.module_key = module_key
        self.request_staleness = request_staleness
        self.blockchain_cache = blockchain_cache
        self.host_key = host_key
        self.use_testnet = use_testnet

    async def verify(self, request: Request):
        body = await request.body()

        # TODO: we'll replace this by a Result ADT :)
        match self._check_inputs(request, body, self.module_key):
            case (False, error):
                return error
            case (True, _):
                pass

        body_dict: dict[str, dict[str, Any]] = json.loads(body)
        timestamp = body_dict["params"].get("timestamp", None)
        legacy_timestamp = request.headers.get("X-Timestamp", None)
        try:
            timestamp_to_use = (
                timestamp if not legacy_timestamp else legacy_timestamp
            )
            request_time = datetime.fromisoformat(timestamp_to_use)
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid ISO timestamp given"},
            )
        if (
            datetime.now(timezone.utc) - request_time
        ).total_seconds() > self.request_staleness:
            return JSONResponse(
                status_code=400, content={"error": "Request is too stale"}
            )
        return None

    def _check_inputs(
        self, request: Request, body: bytes, module_key: Ss58Address
    ):
        required_headers = ["x-signature", "x-key", "x-crypto"]
        optional_headers = ["x-timestamp"]

        # TODO: we'll replace this by a Result ADT :)
        match self._get_headers_dict(
            request.headers, required_headers, optional_headers
        ):
            case (False, error):
                return (False, error)
            case (True, headers_dict):
                pass

        # TODO: we'll replace this by a Result ADT :)
        match self._check_signature(headers_dict, body, module_key):
            case (False, error):
                return (False, error)
            case (True, _):
                pass

        # TODO: we'll replace this by a Result ADT :)
        match self._check_key_registered(
            self.subnets_whitelist,
            headers_dict,
            self.blockchain_cache,
            self.host_key,
            self.use_testnet,
        ):
            case (False, error):
                return (False, error)
            case (True, _):
                pass

        return (True, None)

    def _get_headers_dict(
        self,
        headers: starlette.datastructures.Headers,
        required: list[str],
        optional: list[str],
    ):
        headers_dict: dict[str, str] = {}
        for required_header in required:
            value = headers.get(required_header)
            if not value:
                code = 400
                return False, json_error(
                    code, f"Missing header: {required_header}"
                )
            headers_dict[required_header] = value
        for optional_header in optional:
            value = headers.get(optional_header)
            if value:
                headers_dict[optional_header] = value

        return True, headers_dict

    def _check_signature(
        self, headers_dict: dict[str, str], body: bytes, module_key: Ss58Address
    ):
        key = headers_dict["x-key"]
        signature = headers_dict["x-signature"]
        crypto = int(headers_dict["x-crypto"])  # TODO: better handling of this

        if not is_hex_string(key):
            reason = "X-Key should be a hex value"
            log_reffusal(key, reason)
            return (False, json_error(400, reason))
        try:
            signature = parse_hex(signature)
        except Exception:
            reason = "Signature sent is not a valid hex value"
            log_reffusal(key, reason)
            return False, json_error(400, reason)
        try:
            key = parse_hex(key)
        except Exception:
            reason = "Key sent is not a valid hex value"
            log_reffusal(key, reason)
            return False, json_error(400, reason)
        # decodes the key for better logging
        key_ss58 = try_ss58_decode(key)
        if key_ss58 is None:
            reason = "Caller key could not be decoded into a ss58address"
            log_reffusal(key.decode(), reason)
            return (False, json_error(400, reason))

        timestamp = headers_dict.get("x-timestamp")
        legacy_verified = False
        if timestamp:
            # tries to do a legacy verification
            json_body = json.loads(body)
            json_body["timestamp"] = timestamp
            stamped_body = json.dumps(json_body).encode()
            legacy_verified = signer.verify(
                key, crypto, stamped_body, signature
            )

        verified = signer.verify(key, crypto, body, signature)
        if not verified and not legacy_verified:
            reason = "Signature doesn't match"
            log_reffusal(key_ss58, reason)
            return (False, json_error(401, "Signatures doesn't match"))

        body_dict: dict[str, dict[str, Any]] = json.loads(body)
        target_key = body_dict["params"].get("target_key", None)
        if not target_key or target_key != module_key:
            reason = "Wrong target_key in body"
            log_reffusal(key_ss58, reason)
            return (False, json_error(401, "Wrong target_key in body"))

        return (True, None)

    def _check_key_registered(
        self,
        subnets_whitelist: list[int] | None,
        headers_dict: dict[str, str],
        blockchain_cache: TTLDict[str, list[Ss58Address]],
        host_key: Keypair,
        use_testnet: bool,
    ):
        key = headers_dict["x-key"]
        if not is_hex_string(key):
            return (False, json_error(400, "X-Key should be a hex value"))
        key = parse_hex(key)

        # TODO: checking for key being registered should be smarter
        # e.g. query and store all registered modules periodically.

        ss58 = try_ss58_decode(key)
        if ss58 is None:
            reason = "Caller key could not be decoded into a ss58address"
            log_reffusal(key.decode(), reason)
            return (False, json_error(400, reason))

        # If subnets whitelist is specified, checks if key is registered in one
        # of the given subnets

        allowed_subnets: dict[int, bool] = {}
        caller_subnets: list[int] = []
        if subnets_whitelist is not None:

            def query_keys(subnet: int):
                try:
                    node_url = get_node_url(None, use_testnet=use_testnet)
                    client = make_client(
                        node_url
                    )  # TODO: get client from outer context
                    return [*client.query_map_key(subnet).values()]
                except Exception:
                    log("WARNING: Could not connect to a blockchain node")
                    return_list: list[Ss58Address] = []
                    return return_list

            # TODO: client pool for entire module server

            got_keys = False
            no_keys_reason = (
                "Miner could not connect to a blockchain node "
                "or there is no key registered on the subnet(s) {} "
            )
            for subnet in subnets_whitelist:
                get_keys_on_subnet = partial(query_keys, subnet)
                cache_key = f"keys_on_subnet_{subnet}"
                keys_on_subnet = blockchain_cache.get_or_insert_lazy(
                    cache_key, get_keys_on_subnet
                )
                if len(keys_on_subnet) == 0:
                    reason = no_keys_reason.format(subnet)
                    log(f"WARNING: {reason}")
                else:
                    got_keys = True
                if host_key.ss58_address not in keys_on_subnet:
                    log(
                        f"WARNING: This miner is deregistered on subnet {subnet}"
                    )
                else:
                    allowed_subnets[subnet] = True
                if ss58 in keys_on_subnet:
                    caller_subnets.append(subnet)
            if not got_keys:
                return False, json_error(
                    503, no_keys_reason.format(subnets_whitelist)
                )
            if not allowed_subnets:
                log("WARNING: Miner is not registered on any subnet")
                return False, json_error(
                    403, "Miner is not registered on any subnet"
                )

            # searches for a common subnet between caller and miner
            # TODO: use sets
            allowed_subnets = {
                subnet: allowed
                for subnet, allowed in allowed_subnets.items()
                if (subnet in caller_subnets)
            }
            if not allowed_subnets:
                reason = "Caller key is not registered in any subnet that the miner is"
                log_reffusal(ss58, reason)
                return False, json_error(403, reason)
        else:
            # accepts everything
            pass

        return (True, None)


def build_route_class(verifiers: Sequence[AbstractVerifier]) -> type[APIRoute]:
    class CheckListsRoute(APIRoute):
        def get_route_handler(self):
            original_route_handler = super().get_route_handler()

            async def custom_route_handler(
                request: Request,
            ) -> Response | JSONResponse:
                if not request.url.path.startswith("/method"):
                    unhandled_response: Response = await original_route_handler(
                        request
                    )
                    return unhandled_response
                for verifier in verifiers:
                    response = await verifier.verify(request)
                    if response is not None:
                        return response

                original_response: Response = await original_route_handler(
                    request
                )
                return original_response

            return custom_route_handler

    return CheckListsRoute
