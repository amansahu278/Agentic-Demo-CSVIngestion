"""Write the ingestion report (path, decision, reasoning) to a CSV file."""
import csv
from pathlib import Path


def write_report_csv(
    entries: list[dict],
    report_path: str | Path,
) -> dict:
    """
    Write report entries to a CSV with columns: path, decision, reasoning.
    entries: list of {"path": ..., "decision": ..., "reasoning": ...}
    Returns dict with: report_path, error (if any).
    """
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["path", "decision", "reasoning"])
            w.writeheader()
            w.writerows(entries)
        return {"report_path": str(path), "error": None}
    except Exception as e:
        return {"report_path": None, "error": str(e)}
