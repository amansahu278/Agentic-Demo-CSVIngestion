#!/usr/bin/env python3
"""
Process all CSVs in data/incoming with the explicit graph.
Invokes the graph once per file, collects report entries, writes report CSV.
"""
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from src.config import INCOMING_DIR, REPORTS_DIR
from src.logging_config import setup_logging, get_logger
from src.graph_agent import ingestion_graph
from src.tools import write_report_csv


def get_csv_files(directory: Path) -> list[Path]:
    """Return paths to .csv files in directory (non-recursive)."""
    if not directory.exists():
        return []
    return sorted(directory.glob("*.csv"))


def main() -> None:
    setup_logging()
    csv_files = get_csv_files(INCOMING_DIR)
    if not csv_files:
        print(f"No CSV files in {INCOMING_DIR}. Add some and run again.")
        return

    log = get_logger()
    report_entries: list[dict] = []
    for path in csv_files:
        log.info("Processing file: %s", path)
        state = ingestion_graph.invoke({
            "file_path": str(path),
            "report_entries": report_entries,
        })
        report_entries = state.get("report_entries") or []
        log.info("--- end of file: %s ---", path)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    report_path = REPORTS_DIR / f"ingestion_report_{timestamp}.csv"
    result = write_report_csv(report_entries, report_path)
    if result.get("error"):
        print("Error writing report:", result["error"])
    else:
        print(f"Processed {len(csv_files)} file(s). Report: {result['report_path']}")


if __name__ == "__main__":
    main()
