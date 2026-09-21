from collections.abc import Awaitable, Callable

from langgraph.graph import END, START, StateGraph

from app.agents.local_travel import research_local
from app.agents.supervisor import supervise
from app.agents.transport import research_transport
from app.graph.state import AgentState
from app.services.context import RunContext

Node = Callable[[AgentState, RunContext], Awaitable[dict]]


def build_graph(context: RunContext, planner: Node, critic: Node):
    graph = StateGraph(AgentState)

    def bind(fn: Node):
        async def node(state: AgentState) -> dict:
            context.budget.check()
            result = await fn(state, context)
            return {**result, "agent_trace": list(context.trace)}

        return node

    graph.add_node("supervisor", bind(supervise))
    graph.add_node("transport", bind(research_transport))
    graph.add_node("local", bind(research_local))
    graph.add_node("planner", bind(planner))
    graph.add_node("critic", bind(critic))
    graph.add_edge(START, "supervisor")

    def route(state: AgentState) -> str:
        if state.get("status") == "needs_clarification":
            return END
        if state.get("replanning_count", 0):
            return "planner"
        return "transport" if "Transport" in state.get("routing_plan", []) else "local"

    graph.add_conditional_edges("supervisor", route, [END, "planner", "transport", "local"])
    graph.add_edge("transport", "local")
    graph.add_edge("local", "planner")
    graph.add_edge("planner", "critic")
    graph.add_conditional_edges(
        "critic", lambda s: "supervisor" if s.get("status") == "running" else END, ["supervisor", END]
    )
    return graph.compile()
