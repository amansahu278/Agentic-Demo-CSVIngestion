"""Write the ingestion report (path, decision, reasoning, usage) to a CSV file."""
import csv
from pathlib import Path

REPORT_FIELDS = [
    "path",
    "decision",
    "reasoning",
    "llm_calls",
    "tool_calls",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
]


def write_report_csv(
    entries: list[dict],
    report_path: str | Path,
) -> dict:
    """
    Write report entries to a CSV. Columns: path, decision, reasoning, plus
    llm_calls, tool_calls, prompt_tokens, completion_tokens, total_tokens when present.
    Returns dict with: report_path, error (if any).
    """
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=REPORT_FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(entries)
        return {"report_path": str(path), "error": None}
    except Exception as e:
        return {"report_path": None, "error": str(e)}
