"""
Server for Commune modules.
"""


from typing import Any, Callable

import fastapi
from fastapi import HTTPException, Request
from pydantic import BaseModel
from substrateinterface import Keypair  # type: ignore

# from scalecodec.base import ScaleBytes  # type: ignore
# from scalecodec.utils.ss58 import ss58_decode  # type: ignore
# from substrateinterface import KeypairType  # type: ignore
# from substrateinterface.exceptions import ConfigurationError  # type: ignore
# from substrateinterface.utils.ecdsa_helpers import ecdsa_sign  # type: ignore
# from substrateinterface.utils.ecdsa_helpers import ecdsa_verify  # type: ignore

from communex.module import _signer as signer
from communex.module.module import Module, endpoint


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


class ModuleServer:
    def __init__(
            self,
            module: Module,
            key: Keypair,
            max_request_staleness: int=60,
            ) -> None:
        self._module = module
        self._app = fastapi.FastAPI()
        self.register_endpoints()
        self.register_middleware()
        self.key = key
        self.max_request_staleness = max_request_staleness

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
        async def input_middleware(request: Request, call_next: Callable[[Any], Any]):
            body = await peek_body(request)
            signature = request.headers.get('X-Signature')
            if not signature:
                raise HTTPException(
                    status_code=400,
                    detail="Field 'X-Signature' not included in headers"
                    )
            signature = parse_hex(signature)
            verified = signer.verify(self.key, body, signature)
            if not verified:
                raise HTTPException(
                    status_code=401,
                    detail="Signatures doesn't match"
                    )

            response = await call_next(request)
            return response

        self._app.middleware('http')(input_middleware)


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
