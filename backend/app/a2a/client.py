import asyncio
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import a2a_pb2 as wire
from a2a.utils.constants import TransportProtocol
from google.protobuf.json_format import MessageToDict

from app.a2a.schemas import SpecialistReply, SpecialistRequest, SpecialistState
from app.a2a.service import SKILLS, data_part
from app.core.errors import ControlledError
from app.harness.runtime import TOOL_NAMES


async def discover_card(http, url: str, role: str):
    try:
        card = await A2ACardResolver(http, url).get_agent_card()
        if not set(SKILLS[role]) <= {s.id for s in card.skills}:
            raise ControlledError("INVALID_OUTPUT")
        endpoints = [
            i.url for i in card.supported_interfaces if i.protocol_binding == TransportProtocol.JSONRPC
        ]
        if endpoints != [url.rstrip("/") + "/"]:
            raise ControlledError("INVALID_OUTPUT")
        return card
    except ControlledError:
        raise
    except httpx.TimeoutException:
        raise ControlledError("TIMEOUT", retryable=True) from None
    except Exception:  # noqa: BLE001 - sanitize SDK/provider boundary
        raise ControlledError("PROVIDER_FAILURE", retryable=True) from None


class SpecialistClient:
    def __init__(self, context):
        self.context = context
        self.states = {"transport": "PENDING", "local": "PENDING"}
        self.remote_mcp = {"state": "PENDING", "tools": []}

    async def call(self, role: str, state, fallback):
        ctx = self.context
        rt = ctx.runtime
        url = ctx.settings.a2a_transport_url if role == "transport" else ctx.settings.a2a_local_url
        label = "A2A Transport Agent" if role == "transport" else "A2A Local Travel Agent"
        lease = None
        task_id = None
        client = None
        try:
            async with httpx.AsyncClient(timeout=rt.policy.a2a_timeout_seconds) as http:
                card = await rt.invoke(
                    lambda: discover_card(http, url, role),
                    component="A2A",
                    external=True,
                    timeout=rt.policy.health_timeout_seconds,
                )
                client = ClientFactory(
                    ClientConfig(
                        httpx_client=http,
                        streaming=False,
                        supported_protocol_bindings=[TransportProtocol.JSONRPC],
                    )
                ).create(card)
                cap = (
                    rt.policy.transport_tool_allowance
                    if role == "transport"
                    else rt.policy.local_tool_allowance
                )
                tools = min(cap, ctx.budget.max_tools - ctx.budget.tools)
                external = max(0, ctx.budget.max_external - ctx.budget.external - 1)
                if tools < 1:
                    raise ControlledError("BUDGET_EXHAUSTED")
                request = SpecialistRequest(
                    state=SpecialistState.model_validate(
                        {
                            k: state.get(k, {})
                            for k in ["constraints", "city_schedule", "travel_dates", "evidence"]
                        }
                    ),
                    source_mode="fixture" if ctx.model.name == "fixture" else "live",
                    simulated_rain=ctx.simulated_rain,
                    tool_allowance=tools,
                    external_allowance=external,
                    remaining_seconds=min(ctx.budget.remaining, rt.policy.a2a_timeout_seconds),
                )
                lease = ctx.budget.reserve(tools, external)
                ctx.emit(label, "running", "正在通过 A2A 专家获取结构化研究结果")

                async def send():
                    nonlocal task_id
                    message = wire.Message(
                        message_id=str(uuid4()),
                        role=wire.ROLE_USER,
                        parts=[data_part(request.model_dump(mode="json"))],
                    )
                    async for chunk in client.send_message(wire.SendMessageRequest(message=message)):
                        if chunk.HasField("task"):
                            task = chunk.task
                            task_id = task.id
                            if task.status.state != wire.TASK_STATE_COMPLETED or len(task.artifacts) != 1:
                                raise ControlledError("PROVIDER_FAILURE")
                            parts = task.artifacts[0].parts
                            if len(parts) != 1 or not parts[0].HasField("data"):
                                raise ControlledError("INVALID_OUTPUT")
                            return rt.validate(SpecialistReply, MessageToDict(parts[0].data))
                    raise ControlledError("INVALID_OUTPUT")

                # A whole specialist task is not replayed on ambiguous completion.
                reply = await rt.invoke(
                    send, component="A2A", external=True, timeout=rt.policy.a2a_timeout_seconds, retries=0
                )
            allowed = (
                {"transport_options", "evidence"}
                if role == "transport"
                else {"poi_candidates", "weather_data", "route_data", "evidence"}
            )
            actual = {k for k in type(reply.delta).model_fields if getattr(reply.delta, k) is not None}
            if not actual <= allowed or set(reply.providers) != {"rail" if role == "transport" else "amap"}:
                raise ControlledError("INVALID_OUTPUT")
            ctx.budget.settle(lease, reply.tool_calls, reply.external_calls)
            self.states[role] = "ONLINE"
            self.remote_mcp = {"state": reply.mcp_state, "tools": reply.mcp_tools}
            ctx.remote_provider_status.update(
                {k: v.model_dump(exclude_none=True) for k, v in reply.providers.items()}
            )
            if "amap" in reply.providers and hasattr(ctx.local_provider, "status"):
                ctx.local_provider.status = reply.providers["amap"].state
            for event in reply.runtime_events:
                rt.record(event.component, event.code, event.status)
            for item in reply.tool_observations:
                observation = item.model_dump()
                name = observation.get("tool")
                if name not in TOOL_NAMES:
                    raise ControlledError("INVALID_OUTPUT")
                status = "succeeded" if observation["status"] in {"ok", "empty"} else "failed"
                # These entries are created only after a validated remote artifact.
                ctx.registry.calls.append({"agent": role, **observation, "remote": True})
                if reply.mcp_state == "CONNECTED":
                    ctx.emit("MCP " + TOOL_NAMES[name], status, "A2A 专家已通过 MCP 返回工具结果")
                else:
                    ctx.emit("MCP", "failed", "MCP FALLBACK：专家已使用本地 Provider")
            provider = reply.providers["rail" if role == "transport" else "amap"].state
            ctx.emit(
                "Rail " + provider if role == "transport" else "Amap " + provider,
                "succeeded" if provider in {"LIVE", "DATASET", "MOCK"} else "failed",
                "数据来源由专家实际工具调用结果确认",
            )
            ctx.emit(label, "succeeded", "A2A Task Artifact 已校验并合并到工作流")
            # Preserve existing public activity labels for V0.2 UI consumers.
            ctx.emit("Rail Search" if role == "transport" else "Amap POI", "succeeded", "专家研究已完成")
            return {
                k: getattr(reply.delta, k)
                for k in type(reply.delta).model_fields
                if getattr(reply.delta, k) is not None
            }
        except asyncio.CancelledError:
            if client and task_id:
                try:
                    await asyncio.wait_for(client.cancel_task(wire.CancelTaskRequest(id=task_id)), 1)
                except Exception:  # noqa: BLE001 - sanitize SDK/provider boundary
                    rt.record("A2A", "CANCEL_UNCONFIRMED")
            raise
        except ControlledError as exc:
            self.states[role] = "FALLBACK"
            rt.record("A2A", exc.error.code)
            if exc.error.code in {"BUDGET_EXHAUSTED", "CANCELLED", "DEADLINE_EXCEEDED"}:
                raise
            return await rt.fallback(lambda: fallback(state, ctx), "A2A")
