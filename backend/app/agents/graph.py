from langgraph.graph import StateGraph, END
from langgraph.types import Send
from app.agents.state import AgentState
from app.agents.supervisor import supervisor_node
from app.agents.telemetry_agent import telemetry_agent
from app.agents.strategy_agent import strategy_agent
from app.agents.rag_agent import rag_agent
from app.agents.aggregator import aggregator_node

def route_to_agents(state: AgentState):
    """
    Conditional edge after supervisor: fan out to every agent in state['route'].
    Each Send carries a *fresh copy* of shared read-only fields, but the
    agent functions only ever set ONE output key each, so there's no
    concurrent-write collision on the *_output fields.
    The remaining collision (query, session_id, session_key, route all being
    written identically by every branch) is solved with reducers below.
    """
    route = state.get("route") or ["rag"]
    return [Send(agent_name, state) for agent_name in route]

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("telemetry", telemetry_agent)
    graph.add_node("strategy", strategy_agent)
    graph.add_node("rag", rag_agent)
    graph.add_node("aggregator", aggregator_node)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_to_agents,
        ["telemetry", "strategy", "rag"],
    )

    graph.add_edge("telemetry", "aggregator")
    graph.add_edge("strategy", "aggregator")
    graph.add_edge("rag", "aggregator")

    graph.add_edge("aggregator", END)

    return graph.compile()