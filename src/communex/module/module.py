"""
Tools for defining Commune modules.
"""

import inspect
from dataclasses import dataclass
# from functools import wraps
from typing import Any, Callable, Generic, ParamSpec, TypeVar, cast

import fastapi
import pydantic
import uvicorn
from pydantic import BaseModel

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
    def __init__(self, module: Module) -> None:
        self._module = module
        self._app = fastapi.FastAPI()
        self.register_endpoints()

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



if __name__ == "__main__":

    class Amod(Module):
        @endpoint
        def do_the_thing(self, awesomness: int = 42):
            return {"msg": f"Level of awesomness: {awesomness}"}

    a_mod = Amod()
    server = ModuleServer(a_mod)
    app = server.get_fastapi_app()

    uvicorn.run(app, host="127.0.0.1", port=8000)  # type: ignore
