import datetime
from typing import Any, Literal

from fastapi.responses import JSONResponse
from scalecodec.utils.ss58 import ss58_encode  # type: ignore
from communex.key import check_ss58_address


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
        flush: Literal[False] = False
    ):
    print(f"[{iso_timestamp_now()}] " + msg, *values, sep=sep, end=end, file=file, flush=flush)


def log_reffusal(key: str, reason: str):
    log(f"INFO: refusing module {key} request because: {reason}")


def json_error(code: int, message: str):
    return JSONResponse(status_code=code, content={"error": {"code": code, "message": message}})


def try_ss58_decode(key: bytes | str):
    ss58_format = 42
    try:
        ss58 = ss58_encode(key, ss58_format)
        ss58 = check_ss58_address(ss58, ss58_format)
    except Exception:
        return None
    return ss58