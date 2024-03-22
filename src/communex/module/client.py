"""
Client for Commune modules.
"""

import asyncio
import datetime
import json
from typing import Any

import aiohttp
from substrateinterface import Keypair  # type: ignore

from ._signer import sign, TESTING_MNEMONIC


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
        }

        serialized_data = serialize(request_data)
        signature = sign(self.key, serialized_data)
        # signed_data = sign_to_dict(self.key, serialized_data)
        headers = {
            "Content-Type": "application/json",
            "X-Signature": signature.hex(),
            "X-Timestamp": iso_timestamp_now(),
            "X-Key": self.key.public_key.hex(),
            "X-Crypto": str(self.key.crypto_type),
        }
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"http://{self.host}:{self.port}/{fn}",
                json=json.loads(serialized_data),
                headers=headers,
            ) as response:
                match response.status:
                    case 200:
                        pass
                    case _:
                        response_j = await response.json()
                        raise Exception(
                            f"Unexpected status code: {response_j['error']}")
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


if __name__ == "__main__":
    keypair = Keypair.create_from_mnemonic(
        TESTING_MNEMONIC
    )
    client = ModuleClient("localhost", 8000, keypair)
    result = asyncio.run(client.request("method/do_the_thing", {"awesomness": 45}))
    print(result)
