"""
Client for Commune modules.
"""

import asyncio
import json
from typing import Any

import aiohttp
import aiohttp.client_exceptions
import aiohttp.web_exceptions
from substrateinterface import Keypair  # type: ignore

from ._signer import TESTING_MNEMONIC
from ._protocol import create_request_data, create_method_endpoint
from communex.types import Ss58Address
from communex.key import check_ss58_address
from communex.errors import NetworkTimeoutError

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
        serialized_data, headers = create_request_data(self.key, target_key, params)

        out = aiohttp.ClientTimeout(total=timeout)
        try:
            async with aiohttp.ClientSession(timeout=out) as session:
                async with session.post(
                    create_method_endpoint(self.host, self.port, fn),
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
                            raise Exception(
                                f"Unknown content type: {response.content_type}")
        except asyncio.exceptions.TimeoutError as e:
            raise NetworkTimeoutError(
                f"The call took longer than the timeout of {timeout} second(s)").with_traceback(e.__traceback__)


if __name__ == "__main__":
    keypair = Keypair.create_from_mnemonic(
        TESTING_MNEMONIC
    )
    client = ModuleClient("localhost", 8000, keypair)
    ss58_address = check_ss58_address(keypair.ss58_address)
    result = asyncio.run(client.call("do_the_thing", ss58_address, {
                         "awesomness": 45, "extra": "hi"}))
    print(result)
