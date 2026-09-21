import re

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.core.errors import ControlledError

router = APIRouter()


@router.get("/api/map/config")
async def map_config(request: Request) -> dict:
    settings = request.app.state.settings
    missing = []
    if not settings.vite_amap_js_key.get_secret_value():
        missing.append("VITE_AMAP_JS_KEY")
    if not settings.vite_amap_security_code.get_secret_value():
        missing.append("VITE_AMAP_SECURITY_CODE")
    return {"configured": not missing, "missing": missing, "service_host": "/_AMapService"}


# Only endpoints required by the map SDK; never an arbitrary URL proxy.
MAP_ENDPOINTS = {
    "v3/log/init": "https://restapi.amap.com/v3/log/init",
    "v4/map/styles": "https://webapi.amap.com/v4/map/styles",
    "v3/vectormap": "https://fmap01.amap.com/v3/vectormap",
    "v4/maps": "https://restapi.amap.com/v4/maps",
}


@router.get("/_AMapService/{path:path}")
async def map_service(path: str, request: Request) -> Response:
    if path not in MAP_ENDPOINTS:
        raise ControlledError("TOOL_DENIED")
    settings = request.app.state.settings
    if not settings.vite_amap_security_code.get_secret_value():
        raise ControlledError("AUTH_REQUIRED")
    params = dict(request.query_params)
    params["key"] = settings.vite_amap_js_key.get_secret_value()
    params["jscode"] = settings.vite_amap_security_code.get_secret_value()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(MAP_ENDPOINTS[path], params=params)
        if response.status_code != 200:
            raise ControlledError("PROVIDER_FAILURE")
        media_type = response.headers.get("content-type", "application/json")
        callback = params.get("callback", "")
        # Some SDK endpoints return JSONP as octet-stream. Preserve nosniff and
        # recognize only the requested, syntactically valid JSONP callback.
        if (
            re.fullmatch(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*", callback)
            and response.content.lstrip().startswith((callback + "(").encode())
        ):
            media_type = "application/javascript"
        return Response(
            response.content,
            media_type=media_type,
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )
    except httpx.TimeoutException:
        raise ControlledError("TIMEOUT") from None
    except httpx.RequestError:
        raise ControlledError("PROVIDER_FAILURE") from None
