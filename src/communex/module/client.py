"""
Client for Commune modules.
"""

import asyncio
import datetime
import json
from typing import Any

import aiohttp
from substrateinterface import Keypair, KeypairType  # type: ignore

import sr25519  # type: ignore


def iso_timestamp_now() -> str:
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    iso_now = now.isoformat()
    return iso_now


def serialize(data: Any) -> bytes:
    txt = json.dumps(data)
    return txt.encode()


class ModuleClient:
    host: str
    port: int
    key: Keypair

    def __init__(self, host: str, port: int, key: Keypair):
        self.host = host
        self.port = port
        self.key = key

    async def request(self, fn: str, params: Any = None) -> Any:
        timeout = 60

        request_data = {
            "params": params,
            "timestamp": iso_timestamp_now(),
        }

        serialized_data = serialize(request_data)
        signed_data = sign(self.key, serialized_data)

        async with aiohttp.ClientSession() as session:
            async with session.post(f"http://{self.host}:{self.port}/{fn}", json=signed_data) as response:
                match response.status:
                    case 200:
                        pass
                    case _:
                        raise Exception(
                            f"Unexpected status code: {response.status} {response.reason}")
                match response.content_type:
                    case 'application/json':
                        result = await asyncio.wait_for(response.json(), timeout=timeout)
                        # TODO: desserialize result
                        return result
                    case _:
                        raise Exception(f"Unknown content type: {response.content_type}")

    def process_output(self, result: Any) -> Any:
        if isinstance(result, str):
            result = json.loads(result)

        # TODO: deserialize result
        return result


def sign(keypair: Keypair, data: bytes) -> bytes:
    match keypair.crypto_type:
        case KeypairType.SR25519:
            signature: bytes = sr25519.sign(  # type: ignore
                (keypair.public_key, keypair.private_key), data)  # type: ignore
        case _:
            raise Exception(f"Crypto type {keypair.crypto_type} not supported")

    return signature  # type: ignore


def sign_with_metadate(keypair: Keypair, data: bytes):
    signature = sign(keypair, data)
    sig_hex: str = signature.hex()
    return {
        'address': keypair.ss58_address,
        'crypto_type': keypair.crypto_type,
        'data': data.decode(),  # TODO: this might fail depending on the string? use b64?
        'signature': sig_hex,
    }
