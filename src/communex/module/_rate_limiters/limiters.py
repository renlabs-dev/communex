from typing import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from keylimiter import TokenBucketLimiter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from pydantic_settings import BaseSettings
from ._stake_limiter import StakeLimiter
from fastapi.routing import APIRoute

Callback = Callable[[Request], Awaitable[Response]]


class IpLimiterParams(BaseSettings):
    bucket_size: int = 15
    refill_rate: int = 1

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
        '''
        :param app: FastAPI instance
        :param limiter: KeyLimiter instance OR None

        If limiter is None, then a default TokenBucketLimiter is used with the following config:
        bucket_size=200, refill_rate=15
        '''
        super().__init__(app)

        # fallback to default limiter
        if not params:
            params = IpLimiterParams()
        self._limiter = TokenBucketLimiter(bucket_size=params.bucket_size, refill_rate=params.refill_rate)

    async def dispatch(self, request: Request, call_next: Callback) -> Response:
        assert request.client is not None, "request is invalid"
        assert request.client.host, "request is invalid."

        ip = request.client.host

        is_allowed = self._limiter.allow(ip)

        if not is_allowed:
            response = JSONResponse(
                status_code=429, 
                headers={"X-RateLimit-Remaining": str(self._limiter.remaining(ip))},
                content={"error": "Rate limit exceeded"}
                )
            return response

        response = await call_next(request)

        return response


def build_stakelimiter_router(
        subnets_whitelist: list[int] | None = [0], 
        params_: StakeLimiterParams | None = None,
    ) -> type[APIRoute]:
    class StakeLimiterRouter(APIRoute):
        def get_route_handler(self):
            original_route_handler = super().get_route_handler()
            
            async def custom_route_hanlder(request: Request):
                if not params_:
                    params = StakeLimiterParams()
                else:
                    params = params_
                limiter = StakeLimiter(
                    subnets_whitelist, 
                    epoch=params.epoch, 
                    max_cache_age=params.cache_age,
                    get_refill_rate=params.get_refill_per_epoch,
                    )

                if request.client is None:
                    response = JSONResponse(
                        status_code=401,
                        content={
                            "error": "Address should be present in request"
                        }
                    )
                    return response
                key = request.headers.get('x-key')
                
                if not key:
                    response = JSONResponse(
                        status_code=401,
                        content={"error": "Valid X-Key not provided on headers"}
                        )
                    return response
                

                is_allowed = await limiter.allow(key)

                if not is_allowed:
                    response = JSONResponse(
                        status_code=429, 
                        headers={"X-RateLimit-TryAfter": f"{str(await limiter.retry_after(key))} seconds"},
                        content={"error": "Rate limit exceeded"}
                        )
                    return response
                response: Response = await original_route_handler(request)
                return response

            return custom_route_hanlder
    return StakeLimiterRouter