"""Graph nodes: each node reads state, calls tool logic, returns state updates.

State semantics: Each node receives the full IngestionState and returns a *partial*
dict. LangGraph merges that dict into the state: only the returned keys are updated;
other keys are unchanged. So returning {"decision": "accepted", "reasoning": "..."}
updates state["decision"] and state["reasoning"]; file_path, columns, etc. stay as-is.
"""
from typing import Literal, cast

from pydantic import BaseModel, SecretStr
from langchain_openai import ChatOpenAI

from src.config import load_mandatory_columns, get_openai_api_key, get_openai_model
from src.logging_config import get_logger
from src.tools import load_csv, validate_columns, move_file_to_pile
from src.graph_agent.state import IngestionState

_log = get_logger()

VALID_DECISIONS = ("accepted", "rejected", "needs_review")


class DecideOutput(BaseModel):
    """LLM output for the decide node."""

    decision: Literal["accepted", "rejected", "needs_review"]
    reasoning: str


class ColumnPair(BaseModel):
    """One suggested mapping: actual column name -> mandatory column name."""

    actual: str
    mandatory: str


class FuzzyMatchOutput(BaseModel):
    """LLM output: which actual columns it thinks correspond to missing mandatory columns."""

    column_pairs: list[ColumnPair]  # fixed schema for OpenAI; we convert to dict
    reasoning: str


def node_load(state: IngestionState) -> IngestionState:
    """Load CSV and put columns/row_count/load_error into state."""
    path = state.get("file_path") or ""
    result = load_csv(path)
    out = {
        "columns": result["columns"],
        "row_count": result.get("row_count", 0),
        "load_error": result.get("error"),
    }
    _log.info("node_load returning: %s", out)
    return out


def node_validate(state: IngestionState) -> IngestionState:
    """Strict validation: are all mandatory columns present?"""
    columns = state.get("columns") or []
    mandatory = load_mandatory_columns()
    result = validate_columns(columns, mandatory)
    out = {"valid": result["valid"], "missing": result["missing"]}
    _log.info("node_validate returning: %s", out)
    return out


def _build_fuzzy_match_prompt(
    actual_columns: list[str],
    mandatory_columns: list[str],
    missing: list[str],
) -> str:
    """Build prompt for LLM to suggest which actual columns correspond to missing mandatory columns."""
    return f"""You are matching CSV column names to required mandatory columns.

Actual columns in the CSV: {actual_columns}
Mandatory columns required: {mandatory_columns}
Mandatory columns that are missing (no exact match in actual): {missing}

For each missing mandatory column, decide if any actual column likely means the same thing (e.g. "cust_id" or "customer_id" for "customer_number", "e-mail" for "email"). If so, give the mapping from that actual column name to the mandatory column name. If no actual column seems to correspond, do not include it in the mapping.

Return a JSON object with exactly two keys:
- "column_pairs": a list of objects, each with "actual" (column name in the CSV) and "mandatory" (required column name it maps to). E.g. [{{"actual": "cust_id", "mandatory": "customer_id"}}]. Only include pairs you think are the same concept. Use the exact strings as they appear in the lists above.
- "reasoning": a short explanation of your choices."""


def node_fuzzy_match(state: IngestionState) -> IngestionState:
    """LLM decides which actual columns correspond to missing mandatory columns (no string-similarity fuzzy)."""
    columns = state.get("columns") or []
    mandatory = load_mandatory_columns()
    missing = state.get("missing") or []

    if not get_openai_api_key():
        out = {
            "mapping": {},
            "all_mandatory_matched": False,
            "unmatched_mandatory": missing,
            "fuzzy_review_reasoning": "No API key; no LLM column matching.",
        }
        _log.info("node_fuzzy_match returning: %s", out)
        return out

    try:
        api_key = get_openai_api_key()
        model = ChatOpenAI(
            model=get_openai_model(),
            api_key=SecretStr(api_key) if api_key else None,
            temperature=0,
        ).with_structured_output(FuzzyMatchOutput)
        prompt = _build_fuzzy_match_prompt(columns, mandatory, missing)
        out = cast(FuzzyMatchOutput, model.invoke(prompt))
        mapping = {p.actual: p.mandatory for p in (out.column_pairs or [])}
        fuzzy_review_reasoning = out.reasoning or "LLM suggested column mapping."

        # Which mandatory columns are now covered? (exact match in actual, or as value in mapping)
        exact_covered = set(columns) & set(mandatory)
        mapped_mandatory = set(mapping.values())
        covered = exact_covered | mapped_mandatory
        unmatched_mandatory = [m for m in mandatory if m not in covered]
        all_mandatory_matched = len(unmatched_mandatory) == 0

        out = {
            "mapping": mapping,
            "all_mandatory_matched": all_mandatory_matched,
            "unmatched_mandatory": unmatched_mandatory,
            "fuzzy_review_reasoning": fuzzy_review_reasoning,
        }
        _log.info("node_fuzzy_match returning: %s", out)
        return out
    except Exception as e:
        out = {
            "mapping": {},
            "all_mandatory_matched": False,
            "unmatched_mandatory": missing,
            "fuzzy_review_reasoning": f"Fuzzy match error: {e!s}.",
        }
        _log.info("node_fuzzy_match returning: %s", out)
        return out


def _build_decide_prompt(state: IngestionState) -> str:
    """Build prompt for LLM from state (handles missing keys when short-circuited)."""
    file_path = state.get("file_path") or ""
    load_error = state.get("load_error")
    valid = state.get("valid", False)
    missing = state.get("missing") or []
    mapping = state.get("mapping") or {}
    all_mandatory_matched = state.get("all_mandatory_matched", False)
    unmatched_mandatory = state.get("unmatched_mandatory") or []
    fuzzy_review_reasoning = state.get("fuzzy_review_reasoning")
    columns = state.get("columns") or []
    row_count = state.get("row_count", 0)

    return f"""You are classifying a CSV file for ingestion.

Context:
- File: {file_path}
- Load error: {load_error if load_error else "None"}
- Columns found: {columns}
- Row count: {row_count}
- Mandatory columns present (strict): {valid}
- Missing (strict): {missing}
- Fuzzy mapping (actual -> mandatory): {mapping}
- All mandatory columns covered by fuzzy: {all_mandatory_matched}
- Unmatched mandatory: {unmatched_mandatory}
- Fuzzy review (LLM accept/reject of mapping): {fuzzy_review_reasoning if fuzzy_review_reasoning else "N/A"}

Respond with JSON only, no other text, with exactly two keys:
- "decision": one of "accepted", "rejected", "needs_review"
- "reasoning": a short explanation for this decision.

Rules: If there was a load error, decision must be "rejected". If all mandatory columns are present (strict), use "accepted". If missing but LLM-suggested mapping covers all mandatory, use "needs_review". Otherwise "rejected"."""


def node_decide(state: IngestionState) -> IngestionState:
    """LLM-based decision: accepted, rejected, or needs_review + reasoning."""
    api_key = get_openai_api_key()
    if not api_key:
        out = {
            "decision": "rejected",
            "reasoning": "LLM error: OPENAI_API_KEY not set.",
        }
        _log.info("node_decide returning: %s", out)
        return out

    try:
        model = ChatOpenAI(
            model=get_openai_model(),
            api_key=SecretStr(api_key) if api_key else None,
            temperature=0,
        ).with_structured_output(DecideOutput)
        prompt = _build_decide_prompt(state)
        out = cast(DecideOutput, model.invoke(prompt))
        decision = out.decision
        reasoning = out.reasoning or "No reasoning provided."
        if decision not in VALID_DECISIONS:
            decision = "rejected"
            reasoning = f"Invalid LLM output: {decision}. {reasoning}"
        out = {"decision": decision, "reasoning": reasoning or "No reasoning provided."}
        _log.info("node_decide returning: %s", out)
        return out
    except Exception as e:
        out = {
            "decision": "rejected",
            "reasoning": f"LLM error: {e!s}.",
        }
        _log.info("node_decide returning: %s", out)
        return out


def node_move(state: IngestionState) -> IngestionState:
    """Move file to the pile indicated by decision."""
    path = state.get("file_path") or ""
    decision = state.get("decision") or "rejected"
    result = move_file_to_pile(path, decision)
    out = {}
    _log.info("node_move returning: %s (move result: %s)", out, result)
    return out


def node_append_report(state: IngestionState) -> IngestionState:
    """Append one report row (path, decision, reasoning) to report_entries."""
    path = state.get("file_path") or ""
    decision = state.get("decision") or "rejected"
    reasoning = state.get("reasoning") or ""
    out = {
        "report_entries": [{"path": path, "decision": decision, "reasoning": reasoning}]
    }
    _log.info("node_append_report returning: %s", out)
    return out
