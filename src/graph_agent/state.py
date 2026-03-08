"""State schema for the CSV ingestion graph."""
from operator import add
from typing import Annotated, TypedDict


class IngestionState(TypedDict, total=False):
    """State passed between graph nodes. All keys optional for partial updates."""

    # Input
    file_path: str

    # From load_csv
    columns: list[str]
    row_count: int
    load_error: str | None

    # From validate_columns
    valid: bool
    missing: list[str]

    # From fuzzy_match (LLM suggests which actual columns map to missing mandatory)
    mapping: dict[str, str]
    all_mandatory_matched: bool
    unmatched_mandatory: list[str]
    fuzzy_review_reasoning: str | None  # LLM reasoning for the suggested mapping

    # From decide (rule-based)
    decision: str  # "accepted" | "rejected" | "needs_review"
    reasoning: str

    # Accumulated report rows (path, decision, reasoning) for this run
    report_entries: Annotated[list[dict], add]
