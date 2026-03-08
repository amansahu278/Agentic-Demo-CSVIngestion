"""Build and compile the CSV ingestion StateGraph."""
from langgraph.graph import START, END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.graph_agent.state import IngestionState
from src.graph_agent import nodes


def route_after_load(state: IngestionState) -> str:
    """If load failed, skip to decide; else run validate."""
    if state.get("load_error"):
        return "decide"
    return "validate"


def route_after_validate(state: IngestionState) -> str:
    """If all mandatory columns present, go to decide; else run fuzzy match."""
    if state.get("valid"):
        return "decide"
    return "fuzzy_match"


def build_graph() -> CompiledStateGraph:
    """Build the ingestion graph: load -> [decide | validate -> [fuzzy_match?] -> decide] -> move -> append_report."""
    builder = StateGraph(IngestionState)

    builder.add_node("load", nodes.node_load)
    builder.add_node("validate", nodes.node_validate)
    builder.add_node("fuzzy_match", nodes.node_fuzzy_match)
    builder.add_node("decide", nodes.node_decide)
    builder.add_node("move", nodes.node_move)
    builder.add_node("append_report", nodes.node_append_report)

    builder.add_edge(START, "load")
    builder.add_conditional_edges(
        "load",
        route_after_load,
        {"decide": "decide", "validate": "validate"},
    )
    builder.add_conditional_edges(
        "validate",
        route_after_validate,
        {"decide": "decide", "fuzzy_match": "fuzzy_match"},
    )
    builder.add_edge("fuzzy_match", "decide")
    builder.add_edge("decide", "move")
    builder.add_edge("move", "append_report")
    builder.add_edge("append_report", END)

    return builder.compile()


# Single compiled graph instance for reuse
ingestion_graph = build_graph()
