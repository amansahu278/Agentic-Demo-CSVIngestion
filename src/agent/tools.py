"""LangChain tools for the single agent. Wrap shared tools and add LLM suggest_column_mapping."""
import json
from typing import cast

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr

from langgraph.config import get_config as get_langgraph_config

from src.config import (
    load_mandatory_columns,
    get_openai_api_key,
    get_openai_model,
)
from src.tools import (
    load_csv as _load_csv,
    validate_columns as _validate_columns,
    normalize_csv_columns as _normalize_csv_columns,
    move_file_to_pile as _move_file_to_pile,
)


class ColumnPair(BaseModel):
    actual: str
    mandatory: str


class SuggestMappingOutput(BaseModel):
    column_pairs: list[ColumnPair]
    reasoning: str


def _suggest_mapping_llm(
    actual_columns: list[str],
    missing_columns: list[str],
) -> dict:
    """Call LLM to suggest which actual columns map to missing mandatory ones. Returns mapping dict and reasoning."""
    mandatory = load_mandatory_columns()
    if not get_openai_api_key():
        return {"mapping": {}, "reasoning": "No API key; cannot suggest mapping.", "error": "no_api_key"}
    prompt = f"""You are matching CSV column names to required mandatory columns.

Actual columns in the CSV: {actual_columns}
Mandatory columns required: {mandatory}
Mandatory columns that are missing (no exact match in actual): {missing_columns}

For each missing mandatory column, decide if any actual column likely means the same thing. Return JSON with:
- "column_pairs": list of {{"actual": "<csv column>", "mandatory": "<required column>"}}
- "reasoning": short explanation. Use exact strings from the lists above."""
    try:
        # Structured output so we get column_pairs + reasoning instead of free text
        model = ChatOpenAI(
            model=get_openai_model(),
            api_key=SecretStr(get_openai_api_key() or ""),
            temperature=0,
        ).with_structured_output(SuggestMappingOutput)
        invoke_kwargs: dict = {}
        if get_langgraph_config is not None:
            try:
                invoke_kwargs["config"] = get_langgraph_config()
            except RuntimeError:
                pass  # not in a graph context; invoke without config
        out = cast(SuggestMappingOutput, model.invoke(prompt, **invoke_kwargs))
        mapping = {p.actual: p.mandatory for p in (out.column_pairs or [])}
        return {"mapping": mapping, "reasoning": out.reasoning or "", "error": None}
    except Exception as e:
        return {"mapping": {}, "reasoning": "", "error": str(e)}


@tool
def load_csv(file_path: str) -> str:
    """Load a CSV file and return its column names and row count. Call this first for a file path."""
    result = _load_csv(file_path)
    if result.get("error"):
        return f"Error: {result['error']}"
    return f"Columns: {result['columns']}. Row count: {result['row_count']}."


@tool
def validate_columns(actual_columns: list[str]) -> str:
    """Check if the CSV has all mandatory columns. Pass the list of column names from load_csv. Returns valid (bool) and missing list."""
    mandatory = load_mandatory_columns()
    result = _validate_columns(actual_columns, mandatory)
    if result["valid"]:
        return "All mandatory columns are present."
    return f"Missing mandatory columns: {result['missing']}."


@tool
def suggest_column_mapping(actual_columns: list[str], missing_columns: list[str]) -> str:
    """Suggest which actual CSV columns might correspond to missing mandatory columns (e.g. cust_id -> customer_id). Use when validate_columns reported missing columns."""
    out = _suggest_mapping_llm(actual_columns, missing_columns)
    if out.get("error"):
        return f"Error: {out['error']}. {out.get('reasoning', '')}"
    if not out.get("mapping"):
        return f"No mapping suggested. {out.get('reasoning', '')}"
    return f"Suggested mapping: {out['mapping']}. Reasoning: {out.get('reasoning', '')}"

# not being used, but shows a feature we could have
@tool
def normalize_csv_columns(file_path: str, column_mapping_json: str) -> str:
    """Rename columns in the CSV using a mapping. column_mapping_json must be a JSON object from actual column name to mandatory name, e.g. {\"cust_id\": \"customer_id\"}. Overwrites the file."""
    try:
        mapping = json.loads(column_mapping_json)
        if not isinstance(mapping, dict):
            return "Error: column_mapping_json must be a JSON object."
        result = _normalize_csv_columns(file_path, mapping)
        if result.get("error"):
            return f"Error: {result['error']}"
        return f"Normalized and saved to {result['output_path']}."
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"


@tool
def move_file_to_pile(file_path: str, pile: str) -> str:
    """Move (copy) the CSV file into a pile: 'accepted', 'rejected', or 'needs_review'. Use needs_review (not accepted) when you applied a fuzzy/suggested column mapping."""
    if pile not in ("accepted", "rejected", "needs_review"):
        return f"Invalid pile. Use one of: accepted, rejected, needs_review."
    result = _move_file_to_pile(file_path, pile)
    if result.get("error"):
        return f"Error: {result['error']}"
    return f"File copied to {result['destination_path']}."


@tool
def append_report_entry(file_path: str, decision: str, reasoning: str) -> str:
    """Record the ingestion decision. Use decision needs_review (not accepted) when suggest_column_mapping was used; accepted only when all mandatory columns were already present. Provide a short reasoning; mapping details are added automatically when applicable."""
    if decision not in ("accepted", "rejected", "needs_review"):
        return f"Invalid decision. Use one of: accepted, rejected, needs_review."
    return "Report entry recorded."


def get_agent_tools() -> list:
    """Return the list of LangChain tools for the agent."""
    return [
        load_csv,
        validate_columns,
        suggest_column_mapping,
        move_file_to_pile,
        append_report_entry,
    ]
