"""
Tools for defining Commune modules.
"""

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Generic, ParamSpec, TypeVar, cast

import pydantic
from pydantic import BaseModel

T = TypeVar('T')
P = ParamSpec('P')


class EndpointParams(BaseModel):
    class config:
        extra = "allow"


@dataclass
class EndpointDefinition(Generic[T, P]):
    name: str
    fn: Callable[P, T]
    params_model: type[EndpointParams]


def endpoint(fn: Callable[P, T]) -> Callable[P, T]:
    sig = inspect.signature(fn)
    params_model = function_params_to_model(sig)
    name = fn.__name__

    endpoint_def = EndpointDefinition(name, fn, params_model)
    fn._endpoint_def = endpoint_def  # type: ignore

    return fn


def function_params_to_model(signature: inspect.Signature) -> type[EndpointParams]:
    fields: dict[str, tuple[type] | tuple[type, Any]] = {}
    for i, param in enumerate(signature.parameters.values()):
        name = param.name
        if name == "self":  # cursed
            assert i == 0
            continue
        annotation = param.annotation
        if annotation == param.empty:
            raise Exception(
                f"Error: annotation for parameter `{name}` not found")

        if param.default == param.empty:
            fields[name] = (annotation, ...)
        else:
            fields[name] = (annotation, param.default)

    model: type[EndpointParams] = cast(

        type[EndpointParams], pydantic.create_model(  #  type: ignore
            'Params', **fields, __base__=EndpointParams)  #  type: ignore
    )

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
