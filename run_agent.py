#!/usr/bin/env python3
"""
Process all CSVs in data/incoming with the single (ReAct) agent.
Invokes the agent once per file; the agent chooses which tools to call and when to stop.
"""
import argparse
import os
import warnings
from pathlib import Path
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from src.config import INCOMING_DIR, REPORTS_DIR, get_agent_recursion_limit
from src.logging_config import setup_logging, get_logger
from src.agent import ingestion_agent
from src.tools import write_report_csv

# Langfuse tracing when credentials are set
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
from langfuse import get_client as get_langfuse_client


# Suppress Pydantic serialization warning from LLM structured output (SuggestMappingOutput, etc.)
warnings.filterwarnings("ignore", message=".*Pydantic serializer.*", category=UserWarning)


def get_csv_files(directory: Path) -> list[Path]:
    """Return paths to .csv files in directory (non-recursive)."""
    if not directory.exists():
        return []
    return sorted(directory.glob("*.csv"))


def usage_from_messages(messages: list) -> dict:
    """From graph state messages, return llm_calls, tool_calls, and token counts (prompt/completion/total)."""
    llm_calls = 0
    tool_calls = 0
    prompt_tokens = 0
    completion_tokens = 0
    for msg in messages or []:
        if isinstance(msg, AIMessage):
            llm_calls += 1
            if getattr(msg, "tool_calls", None):
                tool_calls += len(msg.tool_calls)
            meta = getattr(msg, "usage_metadata", None)
            if meta:
                prompt_tokens += meta.get("input_tokens", 0)
                completion_tokens += meta.get("output_tokens", 0)
    return {
        "llm_calls": llm_calls,
        "tool_calls": tool_calls,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Process CSVs in data/incoming with the ReAct agent.")
    parser.add_argument("--debug", action="store_true", help="Set log level to DEBUG (tool calls, state updates).")
    args = parser.parse_args()

    setup_logging(debug=args.debug)
    log = get_logger()
    csv_files = get_csv_files(INCOMING_DIR)
    if not csv_files:
        log.info(f"No CSV files in {INCOMING_DIR}. Add some and run again.")
        return

    # Optional Langfuse tracing (set LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY in env)
    langfuse_handler = None
    if os.environ.get("LANGFUSE_SECRET_KEY") and LangfuseCallbackHandler is not None:
        langfuse_handler = LangfuseCallbackHandler()
        log.info("Langfuse tracing enabled.")

    # Report rows accumulate across files; each invoke may append via append_report_entry
    report_entries: list[dict] = []
    for path in csv_files:
        log.info("Processing file: %s", path)
        initial = HumanMessage(
            content=f"""Process the CSV at: {path}
Load it, validate its columns against the mandatory list, and decide whether to accept, reject, or flag for needs_review.

Decision rules:
- **accepted**: Only when validate_columns reported "All mandatory columns are present" and you did not use suggest_column_mapping or normalize_csv_columns.
- **needs_review**: When columns were missing and you used suggest_column_mapping and/or normalize_csv_columns (fuzzy mapping). Do not accept such files—they must go to needs_review for human verification.
- **rejected**: When mandatory columns are missing and no reasonable mapping exists (or suggest_column_mapping could not suggest one).

Then move the file to the correct pile and call append_report_entry with the file path, your decision, and a short reasoning."""
        )
        input_state = {"messages": [initial], "report_entries": report_entries}
        log.debug(
            "invoke: input state messages=%d, report_entries=%d",
            len(input_state["messages"]),
            len(input_state["report_entries"]),
        )
        invoke_config: RunnableConfig = {"recursion_limit": get_agent_recursion_limit()}
        if langfuse_handler is not None:
            invoke_config["callbacks"] = [langfuse_handler]
            invoke_config["metadata"] = {"file_path": str(path)}
        state = ingestion_agent.invoke(input_state, config=invoke_config)
        report_entries = state.get("report_entries") or []
        # Attach usage for this file to the report row the agent just appended
        usage = usage_from_messages(state.get("messages") or [])
        if report_entries and (report_entries[-1].get("path") == str(path)):
            report_entries[-1].update(usage)
        log.debug(
            "invoke: output state messages=%d, report_entries=%d",
            len(state.get("messages") or []),
            len(report_entries),
        )
        log.info("--- end of file: %s ---", path)

    if langfuse_handler is not None and get_langfuse_client is not None:
        get_langfuse_client().flush()

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    report_path = REPORTS_DIR / f"ingestion_report_agent_{timestamp}.csv"
    result = write_report_csv(report_entries, report_path)
    if result.get("error"):
        log.info("Error writing report:", result["error"])
    else:
        log.info(f"Processed {len(csv_files)} file(s). Report: {result['report_path']}")


if __name__ == "__main__":
    main()
