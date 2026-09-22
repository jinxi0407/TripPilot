from mcp import Client

from app.core.errors import ControlledError
from app.harness.runtime import TOOL_NAMES
from app.mcp.schemas import CONTRACTS, MCPReply


class TravelMCPClient:
    def __init__(self, context, source_mode: str):
        self.context = context
        self.runtime = context.runtime
        self.settings = context.settings
        self.source_mode = source_mode
        self.state = "PENDING"
        self.tools: list[str] = []
        self.offline = False
        self.provider_states: dict[str, dict] = {}

    async def discover(self) -> list[str]:
        async def operation():
            try:
                async with Client(
                    self.settings.mcp_url, read_timeout_seconds=self.runtime.policy.mcp_timeout_seconds
                ) as client:
                    response = await client.list_tools()
                names = sorted(t.name for t in response.tools)
                if names != sorted(CONTRACTS):
                    raise ControlledError("INVALID_OUTPUT")
                return names
            except ControlledError:
                raise
            except Exception:  # noqa: BLE001 - sanitize SDK/provider boundary
                raise ControlledError("PROVIDER_FAILURE", retryable=True) from None

        self.tools = await self.runtime.invoke(
            operation, component="MCP", external=True, timeout=self.runtime.policy.mcp_timeout_seconds
        )
        self.state = "CONNECTED"
        return self.tools

    async def call(self, name: str, query, local_handler, is_external: bool):
        canonical = TOOL_NAMES[name]
        if self.offline:
            return await self.local_fallback(local_handler, query, is_external)
        try:
            if not self.tools:
                await self.discover()
            self.context.emit("MCP " + canonical, "running", "正在通过 MCP 查询旅行数据")
            # Reserve the provider's possible outbound operation before sending.
            # On unknown completion, keep it charged rather than refunding it.
            remote_external = (
                canonical not in {"search_rail", "search_flights"} and self.source_mode == "live"
            )
            if remote_external:
                self.runtime.consume("external")

            async def remote_call():
                arguments = {"query": query.model_dump(mode="json"), "source_mode": self.source_mode}
                if canonical == "get_weather":
                    arguments["simulated_rain"] = self.context.simulated_rain
                async with Client(self.settings.mcp_url) as client:
                    response = await client.call_tool(canonical, arguments)
                if response.is_error:
                    raise ControlledError("INVALID_OUTPUT")
                return self.runtime.validate(MCPReply[CONTRACTS[canonical][1]], response.structured_content)

            reply = await self.runtime.invoke(
                remote_call,
                component="MCP",
                external=True,
                timeout=self.runtime.policy.mcp_timeout_seconds,
                retries=0,
            )
            if reply.external_calls > int(remote_external):
                raise ControlledError("INVALID_OUTPUT")
            if remote_external and reply.external_calls == 0:
                self.context.budget.external -= 1
            key = {"search_rail": "rail", "search_flights": "flight", "search_hotels": "hotel"}.get(
                canonical, "amap"
            )
            self.provider_states[key] = {"state": reply.provider_state}
            self.context.remote_provider_status.update(self.provider_states)
            if key in {"amap", "hotel"} and hasattr(self.context.local_provider, "status"):
                self.context.local_provider.status = reply.provider_state
            if reply.result.status == "error" and reply.result.error:
                raise ControlledError(reply.result.error.code, reply.result.error.retryable)
            self.context.emit("MCP " + canonical, "succeeded", "MCP 工具返回已验证结构化结果")
            return reply.result
        except ControlledError as exc:
            self.runtime.record("MCP", exc.error.code)
            if exc.error.code in {
                "BUDGET_EXHAUSTED",
                "CANCELLED",
                "DEADLINE_EXCEEDED",
                "AUTH_REQUIRED",
                "INVALID_INPUT",
                "INVALID_OUTPUT",
            }:
                raise
            self.state = "FALLBACK"
            self.offline = True
            return await self.local_fallback(local_handler, query, is_external)

    async def local_fallback(self, handler, query, external):
        async def operation():
            if external:
                self.runtime.consume("external")
            result = await handler(query)
            key = "amap" if external else "rail"
            if external:
                self.context.remote_provider_status[key] = {
                    "state": getattr(self.context.local_provider, "status", "FAILED")
                }
            return result

        self.state = "FALLBACK"
        return await self.runtime.fallback(operation, "MCP")

    def attach(self):
        for name, tool in self.context.registry.tools.items():
            original, external = tool.handler, tool.external

            async def handler(query, name=name, original=original, external=external):
                return await self.call(name, query, original, external)

            tool.handler = handler
            tool.external = False  # MCP gateway counts protocol/provider costs separately.
            tool.timeout = max(
                self.runtime.policy.mcp_timeout_seconds, self.runtime.policy.tool_timeout_seconds
            ) * (self.runtime.policy.max_retries + 2)

    def snapshot(self):
        return {"state": self.state, "tools": self.tools}
