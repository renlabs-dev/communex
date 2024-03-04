"""
Tools for defining Commune modules.
"""

import inspect
from typing import Any, Callable, ParamSpec, TypeVar, cast

import pydantic
from pydantic import BaseModel

T = TypeVar('T')
P = ParamSpec('P')


def endpoint(fn: Callable[P, T]) -> Callable[P, T]:
    sig = inspect.signature(fn)
    model = function_params_to_model(sig)
    print(model)

    def wrapper(*args: P.args, **kwargs: P.kwargs):
        fn_return = fn(*args, **kwargs)
        return fn_return

    return wrapper


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
    pass

