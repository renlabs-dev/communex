from typing import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from keylimiter import TokenBucketLimiter
from pydantic_settings import BaseSettings
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

Callback = Callable[[Request], Awaitable[Response]]


class IpLimiterParams(BaseSettings):
    bucket_size: int = 15
    refill_rate: float = 1

    class config:
        env_prefix = "CONFIG_IP_LIMITER_"
        extra = "ignore"


class StakeLimiterParams(BaseSettings):
    epoch: int = 800
    cache_age: int = 600
    get_refill_per_epoch: Callable[[int], float] | None = None
    token_ratio: int = 1

    class config:
        env_prefix = "CONFIG_STAKE_LIMITER_"
        extra = "ignore"


class IpLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        params: IpLimiterParams | None,
    ):
        """
        :param app: FastAPI instance
        :param limiter: KeyLimiter instance OR None

        If limiter is None, then a default TokenBucketLimiter is used with the following config:
        bucket_size=200, refill_rate=15
        """
        super().__init__(app)

        # fallback to default limiter
        if not params:
            params = IpLimiterParams()
        self._limiter = TokenBucketLimiter(
            bucket_size=params.bucket_size, refill_rate=params.refill_rate
        )

    async def dispatch(self, request: Request, call_next: Callback) -> Response:
        assert request.client is not None, "request is invalid"
        assert request.client.host, "request is invalid."

        ip = request.client.host

        is_allowed = self._limiter.allow(ip)

        if not is_allowed:
            response = JSONResponse(
                status_code=429,
                headers={
                    "X-RateLimit-Remaining": str(self._limiter.remaining(ip))
                },
                content={"error": "Rate limit exceeded"},
            )
            return response

        response = await call_next(request)

        return response
