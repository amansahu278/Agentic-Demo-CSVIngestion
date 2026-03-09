"""Build the ReAct agent graph: agent node + tools node, with report_entries accumulation."""
import json
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.config import get_config as get_langgraph_config
from langgraph.graph import START, END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import SecretStr

from src.agent.state import AgentState
from src.agent.tools import get_agent_tools
from src.config import get_openai_api_key, get_openai_model
from src.logging_config import get_logger


def agent_node(state: AgentState) -> dict:
    """Agent node: invoke LLM with messages; return new AIMessage (may have tool_calls)."""
    log = get_logger()
    messages = state.get("messages") or []
    log.debug("agent_node: invoking LLM with %d message(s)", len(messages))
    tools = get_agent_tools()
    llm = ChatOpenAI(
        model=get_openai_model(),
        api_key=SecretStr(get_openai_api_key() or ""),
        temperature=0,
    ).bind_tools(tools)  # LLM can request any of load_csv, validate_columns, etc.
    response = llm.invoke(messages)
    log.debug("agent_node: response %s", response)
    if response.tool_calls:
        names = [tc.get("name") for tc in response.tool_calls]
        log.debug("agent_node: LLM requested tool_calls: %s", names)
    else:
        log.debug("agent_node: LLM returned final message (no tool_calls)")
    return {"messages": [response]}


def _parse_tool_call_args(tool_call: Any) -> dict[str, Any]:
    """Get a normalised dict of arguments from a single tool call (ToolCall is dict-like)."""
    args = tool_call.get("args") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}
    return args if isinstance(args, dict) else {}


def _execute_tool(
    tool_name: str,
    args: dict[str, Any],
    tools_by_name: dict[str, Any],
    runnable_config: RunnableConfig | None = None,
) -> str:
    """Run one tool by name with the given args; return its result as a string for the LLM."""
    tool = tools_by_name.get(tool_name)
    if not tool:
        return f"Unknown tool: {tool_name}"
    try:
        invoke_kwargs: dict = {}
        if runnable_config is not None:
            invoke_kwargs["config"] = runnable_config
        result = tool.invoke(args, **invoke_kwargs)
        return result if isinstance(result, str) else str(result)
    except Exception as e:
        return f"Error: {e}"


def _maybe_report_entry(tool_name: str, args: dict[str, Any]) -> dict[str, str] | None:
    """If this was append_report_entry, return one report row dict; otherwise None."""
    if tool_name != "append_report_entry":
        return None
    return {
        "path": args.get("file_path", ""),
        "decision": args.get("decision", "rejected"),
        "reasoning": args.get("reasoning", ""),
    }


def tools_node(state: AgentState) -> dict:
    """
    Tools node: run every tool call from the last AI message and return their results.

    1. The last message must be an AIMessage with tool_calls; otherwise we return nothing.
    2. For each tool call we: parse args, run the tool, and create a ToolMessage with the result.
    3. If the tool was append_report_entry, we also add one row to report_entries for the report CSV.
    """
    messages = state.get("messages") or []
    last_message = messages[-1]

    # Only run tools when the agent just asked for them (last message has tool_calls)
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {}

    log = get_logger()
    try:
        runnable_config = get_langgraph_config()
    except RuntimeError:
        runnable_config = None  # not in a graph context (e.g. tests)

    tools_by_name = {t.name: t for t in get_agent_tools()}
    new_tool_messages = []
    new_report_rows = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call.get("name")
        tool_call_id = tool_call.get("id") or ""

        args = _parse_tool_call_args(tool_call)
        log.debug("tools_node: calling tool %s with args %s", tool_name, args)
        result_text = _execute_tool(tool_name, args, tools_by_name, runnable_config)
        log.debug("tools_node: %s -> %s", tool_name, result_text)
        new_tool_messages.append(
            ToolMessage(content=result_text, tool_call_id=tool_call_id)
        )

        report_row = _maybe_report_entry(tool_name, args)
        if report_row is not None:
            new_report_rows.append(report_row)
            log.debug("tools_node: state update report_entries += %s", report_row)

    out = {"messages": new_tool_messages}
    if new_report_rows:
        out["report_entries"] = new_report_rows
    log.debug(
        "tools_node: state update messages += %d ToolMessage(s), report_entries += %d",
        len(new_tool_messages),
        len(new_report_rows),
    )
    return out


def _should_continue(state: AgentState) -> str:
    """Route: if last message has tool_calls, go to tools; else end."""
    messages = state.get("messages") or []
    last = messages[-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def build_agent() -> CompiledStateGraph:
    """Build and compile the ReAct agent graph."""
    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tools_node)
    builder.add_edge(START, "agent")
    # If agent returned tool_calls, go to tools; else END. Tools always loop back to agent.
    builder.add_conditional_edges("agent", _should_continue)
    builder.add_edge("tools", "agent")
    return builder.compile()


ingestion_agent = build_agent()
