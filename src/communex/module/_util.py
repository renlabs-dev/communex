import datetime
import random
import sys
from time import sleep
from typing import Any, Callable, Literal, ParamSpec, TypeVar

from fastapi.responses import JSONResponse
from scalecodec.utils.ss58 import ss58_encode

from communex.client import CommuneClient
from communex.key import check_ss58_address

T = TypeVar("T")
T1 = TypeVar("T1")
T2 = TypeVar("T2")

P = ParamSpec("P")
R = TypeVar("R")


def iso_timestamp_now() -> str:
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    iso_now = now.isoformat()
    return iso_now


def log(
    msg: str,
    *values: object,
    sep: str | None = " ",
    end: str | None = "\n",
    file: Any | None = None,
    flush: Literal[False] = False,
):
    print(
        f"[{iso_timestamp_now()}] " + msg,
        *values,
        sep=sep,
        end=end,
        file=file,
        flush=flush,
    )


def log_reffusal(key: str, reason: str):
    log(f"INFO: refusing module {key} request because: {reason}")


def json_error(code: int, message: str):
    return JSONResponse(
        status_code=code, content={"error": {"code": code, "message": message}}
    )


def try_ss58_decode(key: bytes | str):
    ss58_format = 42
    try:
        ss58 = ss58_encode(key, ss58_format)
        ss58 = check_ss58_address(ss58, ss58_format)
    except Exception:
        return None
    return ss58


def retry(max_retries: int | None, retry_exceptions: list[type]):
    assert max_retries is None or max_retries > 0

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        def wrapper(*args: P.args, **kwargs: P.kwargs):
            max_retries__ = (
                max_retries or sys.maxsize
            )  # TODO: fix this ugly thing
            for tries in range(max_retries__ + 1):
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    if any(
                        isinstance(e, exception_t)
                        for exception_t in retry_exceptions
                    ):
                        func_name = func.__name__
                        log(
                            f"An exception occurred in '{func_name} on try {tries}': {e}, but we'll retry."
                        )
                        if tries < max_retries__:
                            delay = (1.4**tries) + random.uniform(0, 1)
                            sleep(delay)
                            continue
                    raise e
            raise Exception("Unreachable")

        return wrapper

    return decorator


@retry(5, [Exception])
def make_client(node_url: str):
    return CommuneClient(
        url=node_url, num_connections=1, wait_for_finalization=False
    )
