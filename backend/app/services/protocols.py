import asyncio

import httpx

from app.a2a.client import SpecialistClient, discover_card
from app.mcp.client import TravelMCPClient


class ProtocolRuntime:
    def __init__(self, context, source_mode: str):
        self.mcp = TravelMCPClient(context, source_mode)
        self.mcp.attach()
        self.a2a = SpecialistClient(context)

    def snapshot(self):
        local, remote = self.mcp.snapshot(), self.a2a.remote_mcp
        mcp = local if local["state"] != "PENDING" else remote
        if remote["state"] == "FALLBACK":
            mcp = remote
        return {"mcp": mcp, "a2a": dict(self.a2a.states)}


async def runtime_health(settings):
    from app.services.engine import create_context

    context = create_context(settings.model_copy(update={"protocols_enabled": False}), mode="fixture")
    gateway = TravelMCPClient(context, "fixture")
    timeout = settings.runtime_policy.health_timeout_seconds

    async def mcp():
        try:
            async with asyncio.timeout(timeout):
                await gateway.discover()
            return gateway.snapshot()
        except Exception:  # noqa: BLE001 - sanitize SDK/provider boundary
            return {"state": "OFFLINE", "tools": []}

    async def a2a(role, url):
        try:
            async with asyncio.timeout(timeout):
                async with httpx.AsyncClient(timeout=timeout) as client:
                    card = await discover_card(client, url, role)
            return {"state": "ONLINE", "skills": [s.id for s in card.skills]}
        except Exception:  # noqa: BLE001 - sanitize SDK/provider boundary
            return {"state": "OFFLINE", "skills": []}

    if settings.protocols_enabled:
        m, t, l = await asyncio.gather(
            mcp(), a2a("transport", settings.a2a_transport_url), a2a("local", settings.a2a_local_url)
        )
    else:
        m = {"state": "DISABLED", "tools": []}
        t = l = {"state": "DISABLED", "skills": []}
    return {
        "mcp": m,
        "a2a": {"transport": t["state"], "local": l["state"]},
        "a2a_transport": t,
        "a2a_local": l,
        "harness": {"state": "ACTIVE", "policy": settings.runtime_policy.model_dump()},
    }
