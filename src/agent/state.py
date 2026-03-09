"""State for the single (ReAct) agent graph."""
from operator import add
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """State: messages (conversation + tool results) and accumulated report entries."""

    # add_messages appends and dedupes; add concatenates lists (report rows)
    messages: Annotated[list[BaseMessage], add_messages]
    report_entries: Annotated[list[dict], add]
