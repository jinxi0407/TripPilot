import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import a2a_pb2 as wire
from a2a.utils.constants import PROTOCOL_VERSION_CURRENT, TransportProtocol
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Value
from starlette.applications import Starlette

from app.a2a.schemas import SpecialistDelta, SpecialistReply, SpecialistRequest
from app.agents.local_travel import research_local
from app.agents.transport import research_transport
from app.core.config import Settings
from app.core.logging import configure_logging
from app.mcp.client import TravelMCPClient
from app.services.engine import create_context

SKILLS = {
    "transport": ["rail-search", "transfer-analysis", "transport-feasibility"],
    "local": ["poi-search", "weather-search", "local-route-planning", "distance-calculation"],
}
NAMES = {"transport": "TripPilot Transport Agent", "local": "TripPilot Local Travel Agent"}


def data_part(data: dict) -> wire.Part:
    return wire.Part(data=ParseDict(data, Value()), media_type="application/json")


def agent_card(role: str, settings: Settings) -> wire.AgentCard:
    url = settings.a2a_transport_url if role == "transport" else settings.a2a_local_url
    return wire.AgentCard(
        name=NAMES[role],
        description="TripPilot existing specialist through A2A and MCP",
        version="1.1.0",
        capabilities=wire.AgentCapabilities(streaming=False),
        supported_interfaces=[
            wire.AgentInterface(
                url=url + "/",
                protocol_binding=TransportProtocol.JSONRPC,
                protocol_version=PROTOCOL_VERSION_CURRENT,
            )
        ],
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        skills=[wire.AgentSkill(id=s, name=s, description=s, tags=["travel", role]) for s in SKILLS[role]],
    )


class SpecialistExecutor(AgentExecutor):
    def __init__(self, role: str, settings: Settings):
        self.role, self.settings = role, settings

    async def execute(self, context, event_queue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await event_queue.enqueue_event(
            wire.Task(
                id=context.task_id,
                context_id=context.context_id,
                status=wire.TaskStatus(state=wire.TASK_STATE_SUBMITTED),
            )
        )
        await updater.start_work()
        try:
            parts = context.message.parts
            if len(parts) != 1 or not parts[0].HasField("data"):
                raise ValueError("Expected a typed data part")
            request = SpecialistRequest.model_validate(MessageToDict(parts[0].data))
            config = self.settings.model_copy(update={"protocols_enabled": False})
            child = create_context(
                config, mode=request.source_mode, scenario="rain" if request.simulated_rain else "normal"
            )
            child.budget.max_tools = min(child.budget.max_tools, request.tool_allowance)
            child.budget.max_external = min(child.budget.max_external, request.external_allowance)
            child.budget.seconds = min(
                child.budget.seconds, request.remaining_seconds, child.runtime.policy.a2a_timeout_seconds
            )
            gateway = TravelMCPClient(child, request.source_mode)
            gateway.attach()
            state = {name: getattr(request.state, name) for name in type(request.state).model_fields}
            async with asyncio.timeout(child.budget.remaining):
                delta = await (research_transport if self.role == "transport" else research_local)(
                    state, child
                )
            providers = child.provider_status()
            providers = {
                k: v
                for k, v in providers.items()
                if k in ({"rail", "flight"} if self.role == "transport" else {"amap", "hotel"})
            }
            reply = SpecialistReply(
                delta=SpecialistDelta.model_validate(delta),
                tool_calls=child.budget.tools,
                external_calls=child.budget.external,
                providers=providers,
                mcp_state=gateway.state,
                mcp_tools=gateway.tools,
                runtime_events=child.runtime.events,
                tool_observations=[
                    {k: call.get(k) for k in ["tool", "status", "cached"]} for call in child.registry.calls
                ],
            )
            await updater.add_artifact(
                [data_part(reply.model_dump(mode="json"))], artifact_id=str(uuid4()), name="specialist-result"
            )
            await updater.complete()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - sanitize SDK/provider boundary
            # The SDK must never receive raw provider exceptions or secret-bearing validation input.
            await updater.failed(
                wire.Message(
                    message_id=str(uuid4()),
                    role=wire.ROLE_AGENT,
                    parts=[wire.Part(text="SPECIALIST_CONTROLLED_FAILURE")],
                )
            )

    async def cancel(self, context, event_queue):
        await TaskUpdater(event_queue, context.task_id, context.context_id).update_status(
            wire.TASK_STATE_CANCELED
        )


def create_service(role: str, settings: Settings | None = None) -> Starlette:
    settings = settings or Settings()
    configure_logging()
    card = agent_card(role, settings)
    handler = DefaultRequestHandler(SpecialistExecutor(role, settings), InMemoryTaskStore(), card)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await handler.aclose()

    return Starlette(
        routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, "/")], lifespan=lifespan
    )


def transport_app():
    return create_service("transport")


def local_app():
    return create_service("local")
