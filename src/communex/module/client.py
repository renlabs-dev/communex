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
from communex.types import Ss58Address
from communex.key import check_ss58_address


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

    async def call(
            self, 
            fn: str,
            target_key: Ss58Address,
            params: Any = {}, 
            timeout: int = 16,
            ) -> Any:
        timestamp = iso_timestamp_now()
        params["target_key"] = target_key
        # params["timestamp"] = timestamp

        request_data = {
            "params": params,
        }

        serialized_data = serialize(request_data)
        request_data["timestamp"] = timestamp
        serialized_stamped_data = serialize(request_data)
        signature = sign(self.key, serialized_stamped_data)

        # signed_data = sign_to_dict(self.key, serialized_data)
        headers = {
            "Content-Type": "application/json",
            "X-Signature": signature.hex(),
            "X-Key": self.key.public_key.hex(),
            "X-Crypto": str(self.key.crypto_type),
            "X-Timestamp": timestamp,
        }
        out = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=out) as session:
            async with session.post(
                f"http://{self.host}:{self.port}/method/{fn}",
                json=json.loads(serialized_data),
                headers=headers,
            ) as response:
                match response.status:
                    case 200:
                        pass
                    case status_code:
                        response_j = await response.json()
                        raise Exception(
                            f"Unexpected status code: {status_code}, response: {response_j}")
                match response.content_type:
                    case 'application/json':
                        result = await asyncio.wait_for(response.json(), timeout=timeout)
                        # TODO: deserialize result
                        return result
                    case _:
                        raise Exception(f"Unknown content type: {response.content_type}")


if __name__ == "__main__":
    keypair = Keypair.create_from_mnemonic(
        TESTING_MNEMONIC
    )
    client = ModuleClient("localhost", 8000, keypair)
    ss58_address = check_ss58_address(keypair.ss58_address)
    result = asyncio.run(client.call("do_the_thing", ss58_address, {"awesomness": 45, "extra": "hi"}))
    print(result)
