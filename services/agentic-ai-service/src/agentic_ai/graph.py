"""Compile LangGraph StateGraph for the five-agent workflow."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from agentic_ai.agents import (
    context_agent_node,
    control_agent_node,
    data_agent_node,
    decision_agent_node,
    signal_agent_node,
)
from agentic_ai.state import WorkflowState

_GRAPH = None


def _route_after_data(state: WorkflowState) -> str:
    if state.get("abort"):
        return "end"
    return "signal_agent"


def build_workflow_graph() -> StateGraph:
    graph = StateGraph(WorkflowState)

    graph.add_node("data_agent", data_agent_node)
    graph.add_node("signal_agent", signal_agent_node)
    graph.add_node("context_agent", context_agent_node)
    graph.add_node("decision_agent", decision_agent_node)
    graph.add_node("control_agent", control_agent_node)

    graph.set_entry_point("data_agent")
    graph.add_conditional_edges(
        "data_agent",
        _route_after_data,
        {"end": END, "signal_agent": "signal_agent"},
    )
    graph.add_edge("signal_agent", "context_agent")
    graph.add_edge("context_agent", "decision_agent")
    graph.add_edge("decision_agent", "control_agent")
    graph.add_edge("control_agent", END)

    return graph


def get_compiled_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_workflow_graph().compile()
    return _GRAPH
