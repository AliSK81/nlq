from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.domain.state import AgentState
from app.graph.nodes import GraphNodes
from app.graph.template import route_after_classify, route_after_retrieve


def build_graph(nodes: GraphNodes):
    graph = StateGraph(AgentState)

    graph.add_node("classify", nodes.classify_node)
    graph.add_node("chitchat", nodes.chitchat_node)
    graph.add_node("retrieve", nodes.retrieve_node)
    graph.add_node("generate_answer", nodes.generate_answer_node)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {"retrieve": "retrieve", "chitchat": "chitchat"},
    )
    graph.add_edge("chitchat", END)
    graph.add_conditional_edges(
        "retrieve",
        route_after_retrieve,
        {"generate_answer": "generate_answer", "retrieve": "retrieve"},
    )
    graph.add_edge("generate_answer", END)

    return graph.compile()


class AgentFactory:
    def __init__(self, compiled_graph) -> None:
        self._graph = compiled_graph

    def run(self, agent_name: str, **state) -> AgentState:
        initial: AgentState = {
            "question": state.get("question", ""),
            "memory_context": state.get("memory_context", ""),
            "prefetched_hits": state.get("prefetched_hits"),
            "request_auth": state.get("request_auth", {}),
            "config": state.get("config", {}),
            "refine_count": 0,
            "steps": [],
            "total_tokens_used": 0,
        }
        return self._graph.invoke(initial)
