from fastapi import Request, Response
from fastapi.routing import APIRoute

from communex.types import Ss58Address
from communex.module._util import log, log_reffusal, json_error, try_ss58_decode


def build_check_lists_route_class(
    blacklist: list[Ss58Address] | None,
    whitelist: list[Ss58Address] | None,
    ip_blacklist: list[str] | None,
) -> type[APIRoute]:

    class CheckListsRoute(APIRoute):
        def get_route_handler(self):
            original_route_handler = super().get_route_handler()

            async def custom_route_handler(request: Request) -> Response:
                if not request.url.path.startswith('/method'):
                    response: Response = await original_route_handler(request)
                    return response
                key = request.headers.get("x-key")
                if not key:
                    reason = "Missing header: X-Key"
                    log(f"INFO: refusing module request because: {reason}")
                    return json_error(400, "Missing header: X-Key")

                ss58 = try_ss58_decode(key)
                if ss58 is None:
                    reason = "Caller key could not be decoded into a ss58address"
                    log_reffusal(key, reason)
                    return json_error(400, reason)
                if request.client is None:
                    return json_error(400, "Address should be present in request")
                if blacklist and ss58 in blacklist:
                    return json_error(403, "You are blacklisted")
                if ip_blacklist and request.client.host in ip_blacklist:
                    return json_error(403, "Your IP is blacklisted")
                if whitelist and ss58 not in whitelist:
                    return json_error(403, "You are not whitelisted")
                response: Response = await original_route_handler(request)
                return response
            
            return custom_route_handler

    return CheckListsRoute

