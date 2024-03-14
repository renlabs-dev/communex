"""
Tools for defining Commune modules.
"""

import inspect
from dataclasses import dataclass
# from functools import wraps
from typing import Any, Callable, Generic, ParamSpec, TypeVar, cast, TypedDict
from copy import deepcopy
import time

import fastapi
from fastapi import Request, HTTPException
import pydantic
import uvicorn
from pydantic import BaseModel
from substrateinterface import Keypair, KeypairType # type: ignore
from scalecodec.base import ScaleBytes  # type: ignore
from scalecodec.utils.ss58 import ss58_decode  # type: ignore
from substrateinterface.exceptions import ConfigurationError # type: ignore
import ed25519_zebra  # type: ignore
import sr25519  # type: ignore
from substrateinterface.utils.ecdsa_helpers import (  # type: ignore
    ecdsa_sign, ecdsa_verify)

from ._signer import SignDict, TESTING_MNEMONIC

T = TypeVar('T')
P = ParamSpec('P')



@dataclass
class EndpointDefinition(Generic[T, P]):
    name: str
    fn: Callable[P, T]
    params_model: type[BaseModel]


def endpoint(fn: Callable[P, T]) -> Callable[P, T]:
    sig = inspect.signature(fn)
    params_model = function_params_to_model(sig)
    name = fn.__name__

    endpoint_def = EndpointDefinition(name, fn, params_model)

    # @wraps(fn)
    # def wrapper(*args: P.args, **kwargs: P.kwargs):
    #     answer = fn(*args, **kwargs)
    #     return answer

    fn._endpoint_def = endpoint_def  # type: ignore

    return fn


def function_params_to_model(signature: inspect.Signature) -> type[BaseModel]:
    fields: dict[str, tuple[type] | tuple[type, Any]] = {}
    for i, param in enumerate(signature.parameters.values()):
        name = param.name
        if name == "self":  # cursed
            assert i == 0
            continue
        annotation = param.annotation
        if annotation == param.empty:
            raise Exception(f"Error: annotation for parameter `{name}` not found")

        if param.default == param.empty:
            fields[name] = (annotation, ...)
        else:
            fields[name] = (annotation, param.default)

    model: type[BaseModel] = cast(
        type[BaseModel], pydantic.create_model('Params', **fields))  # type: ignore

    return model


class Module:
    def __init__(self) -> None:
        # TODO: is it possible to get this at class creation instead of object instantiation?
        self.__endpoints = self.extract_endpoints()

    def get_endpoints(self):
        return self.__endpoints

    def extract_endpoints(self):
        endpoints: dict[str, EndpointDefinition[Any, Any]] = {}
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(method, '_endpoint_def'):
                endpoint_def: EndpointDefinition = method._endpoint_def  # type: ignore
                endpoints[name] = endpoint_def  # type: ignore
        return endpoints

class ModuleServer:
    def __init__(
            self, module: Module,
            key: Keypair,
            max_request_staleness: int=60,
            ) -> None:
        self._module = module
        self._app = fastapi.FastAPI()
        self.register_endpoints()
        self.register_middleware()
        self.key = key
        self.max_request_staleness = max_request_staleness

    async def _set_body(self, request: Request, body: bytes):
        async def receive():
            return {"type": "http.request", "body": body}
        request._receive = receive
 
    async def _get_body(self, request: Request) -> bytes:
        body = await request.body()
        await self._set_body(request, body)
        return body


    def _verify(
            self,
            keypair: Keypair,
            data: ScaleBytes | bytes | str | SignDict,
            signature: bytes | str,
    ) -> bool:
        # TODO: simplify this function

        """
        Verifies data with specified signature

        Parameters
        ----------
        data: data to be verified in `Scalebytes`, bytes or hex string format, or commune dict format
        signature: signature in bytes or hex string format
        public_key: public key in bytes or hex string format

        Returns
        -------
        True if data is signed with this Keypair, otherwise False
        """
        data = deepcopy(data)


        public_key = None
        crypto_type = None

        if isinstance(data, dict):
            # TODO: Check if this asserts makes sense as below the code is accessing those keys
            assert "address" in data, "address not included"
            assert "signature" in data, "signature not included"
            assert "crypto_type" in data, "crypto_type type not included"

            public_key = ss58_decode(data['address'])
            crypto_type = int(data['crypto_type'])
            signature = data['signature']
            if 'data' in data:
                data = data['data']

        if public_key is None:
            public_key = keypair.public_key
        if crypto_type is None:
            crypto_type = keypair.crypto_type

        if isinstance(public_key, str):
            public_key = bytes.fromhex(public_key.replace('0x', ''))

        if isinstance(data, ScaleBytes):
            data = bytes(data.data)
        elif isinstance(data, str) and data[0:2] == '0x':
            data = bytes.fromhex(data[2:])  # type: ignore
        elif isinstance(data, str):
            data = data.encode()

        if isinstance(signature, str) and signature[0:2] == '0x':
            signature = bytes.fromhex(signature[2:])
        elif isinstance(signature, str):
            signature = bytes.fromhex(signature)

        if not isinstance(signature, bytes):
            raise TypeError("Signature should be of type bytes or a hex-string")

        if crypto_type == KeypairType.SR25519:
            crypto_verify_fn = sr25519.verify  # type: ignore
        elif crypto_type == KeypairType.ED25519:
            crypto_verify_fn = ed25519_zebra.ed_verify  # type: ignore
        elif crypto_type == KeypairType.ECDSA:
            crypto_verify_fn = ecdsa_verify  # type: ignore
        else:
            raise ConfigurationError("Crypto type not supported")

        print(public_key, type(public_key))

        verified: bool = crypto_verify_fn(signature, data, public_key)  # type: ignore

        if not verified:
            # Another attempt with the data wrapped, as discussed in https://github.com/polkadot-js/extension/pull/743
            # Note: As Python apps are trusted sources on its own, no need to wrap data when signing from this lib
            verified: bool = crypto_verify_fn(signature, b'<Bytes>' + data + b'</Bytes>', public_key)  # type: ignore

        return verified  # type: ignore

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
        @self._app.middleware('http')
        async def input_middleware(request: Request, call_next: Callable[[Any], Any]):
            body = await self._get_body(request)
            sig = request.headers.get('X-Signature')
            if not sig:
                raise HTTPException(
                    status_code=400, 
                    detail="Field 'X-Signature' not included in headers"
                    )
            
            verified = self._verify(self.key, body, sig)
            if not verified:
                raise HTTPException(
                    status_code=401, 
                    detail="Signatures doesn't match"
                    )
            
            response = await call_next(request)
            return response



if __name__ == "__main__":

    class Amod(Module):
        @endpoint
        def do_the_thing(self, awesomness: int = 42):
            if awesomness > 60:
                msg = f"You're super awesome: {awesomness} awesomness"
            else:
                msg = f"You're not that awesome: {awesomness} awesomness"
            return {"msg": msg}

    a_mod = Amod()
    keypair = Keypair.create_from_mnemonic(TESTING_MNEMONIC)
    server = ModuleServer(a_mod, keypair)
    app = server.get_fastapi_app()

    uvicorn.run(app, host="127.0.0.1", port=8000)  # type: ignore
