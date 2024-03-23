"""
Server for Commune modules.
"""


from typing import Callable, Awaitable
import re

import fastapi
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from substrateinterface import Keypair  # type: ignore
from keylimiter import KeyLimiter
import starlette.datastructures
from starlette.middleware.base import BaseHTTPMiddleware
from scalecodec.utils.ss58 import ss58_encode # type: ignore

from communex.cli._common import make_client
from communex.module._ip_limiter import IpLimiterMiddleware
from communex.module import _signer as signer
from communex.module.module import Module, endpoint
from communex.key import check_ss58_address

def parse_hex(hex_str: str) -> bytes:
    if hex_str[0:2] == '0x':
        return bytes.fromhex(hex_str[2:])
    else:
        return bytes.fromhex(hex_str)


async def peek_body(request: Request) -> bytes:
    """
    Gambiarra to get the body of a request on a middleware, making it available
    to the next handler.
    """
    body = await request.body()

    async def receive():
        return {"type": "http.request", "body": body}
    request._receive = receive  # pyright: ignore [reportPrivateUsage]
    return body


def is_hex_string(string: str):
    # Regular expression to match a hexadecimal string
    hex_pattern = re.compile(r'^[0-9a-fA-F]+$')
    return bool(hex_pattern.match(string))

def _return_error(code: int, message: str):
    return JSONResponse(
        status_code=code, content={
        "error": {
            "code": code,
            "message": message
            }
        }
    )


def _get_headers_dict(headers: starlette.datastructures.Headers, required: list[str]):
    headers_dict: dict[str, str] = {}
    for required_header in required:
        value = headers.get(required_header)
        if not value:
            code = 400
            return False, _return_error(code, f"Missing header: {required_header}")
        headers_dict[required_header] = value
    return True, headers_dict

Callback = Callable[[Request], Awaitable[Response]]
class InputMiddleware(BaseHTTPMiddleware):
    def __init__(
            self,
            app: fastapi.FastAPI,
            subnets: list[int],
    ):
        super().__init__(app)
        self.subnets = subnets

    async def dispatch(self, request: Request, call_next: Callback):
        body = await peek_body(request)
        required_headers = ['x-signature', 'x-key', 'x-crypto']
        success, headers_dict = _get_headers_dict(request.headers, required_headers)
        if not success:
            error = headers_dict
            assert isinstance(error, JSONResponse)
            return error
        assert isinstance(headers_dict, dict)
        
        signature = headers_dict['x-signature']
        key = headers_dict['x-key']
        crypto = int(headers_dict['x-crypto']) #TODO: better handling of this
        is_hex = is_hex_string(key)
        if not is_hex:
            return _return_error(400, "X-Key should be a hex value")
        signature = parse_hex(signature)
        key = parse_hex(key)
        verified = signer.verify(key, crypto, body, signature)
        if not verified:
            return JSONResponse(
                status_code=401,
                content="Signatures doesn't match"
                )

        client = make_client() # TODO: maybe a global client?
        format = 42
        ss58 = ss58_encode(key, format)
        ss58 = check_ss58_address(ss58, format)
        print(self.subnets)
        for subnet in self.subnets:
            uids = client.get_uids(ss58, subnet)
            if not uids:
                return _return_error(403, "Key is not registered on the network")
        response = await call_next(request)
        return response
    

class ModuleServer:
    def __init__(
            self,
            module: Module,
            key: Keypair,
            subnets: list[int],
            max_request_staleness: int = 60,
            ip_limiter: KeyLimiter | None = None,
            whitelist: list[str] | None = None,
            blacklist: list[str] | None = None,
            ) -> None:
        self._module = module
        self._app = fastapi.FastAPI()
        self._subnets = subnets
        self.key = key
        self.register_endpoints()
        self.register_middleware()
        self._app.add_middleware(IpLimiterMiddleware, limiter=ip_limiter)
        self._app.add_middleware(InputMiddleware, subnets=subnets)
        self.max_request_staleness = max_request_staleness
        self._blacklist = blacklist
        self._whitelist = whitelist
    
    
    def get_fastapi_app(self):
        return self._app

    def register_endpoints(self):
        endpoints = self._module.get_endpoints()
        for name, endpoint_def in endpoints.items():
            class Body(BaseModel):
                params: endpoint_def.params_model  # type: ignore
            def handler(body: Body):
                return endpoint_def.fn(self._module, **body.params.model_dump())  # type: ignore
            self._app.post(f"/method/{name}")(handler)

    def register_middleware(self):
        async def check_lists(request: Request, call_next: Callback):
            key = request.headers.get('x-key')
            assert key
            format = 42
            ss58 = ss58_encode(key, format)
            ss58 = check_ss58_address(ss58, format)

            if self._blacklist and ss58 in self._blacklist:
                return _return_error(403, "You are blacklisted")
            if self._whitelist and ss58 not in self._whitelist:
                return _return_error(403, "You are not whitelisted")
            response = await call_next(request)
            return response
        self._app.middleware("http")(check_lists)
    

def main():
    class Amod(Module):
        @endpoint
        def do_the_thing(self, awesomness: int = 42):
            if awesomness > 60:
                msg = f"You're super awesome: {awesomness} awesomness"
            else:
                msg = f"You're not that awesome: {awesomness} awesomness"
            return {"msg": msg}

    a_mod = Amod()
    keypair = Keypair.create_from_mnemonic(signer.TESTING_MNEMONIC)
    server = ModuleServer(a_mod, keypair)
    app = server.get_fastapi_app()

    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)  # type: ignore

if __name__ == "__main__":
    main()
