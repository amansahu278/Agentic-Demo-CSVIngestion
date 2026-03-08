"""Load and inspect a CSV file."""
from pathlib import Path

import pandas as pd


def load_csv(file_path: str | Path) -> dict:
    """
    Read a CSV and return column names and row count.
    Returns dict with keys: columns, row_count, error (if any).
    """
    path = Path(file_path)
    if not path.exists():
        return {"columns": [], "row_count": 0, "error": f"File not found: {path}"}
    try:
        df = pd.read_csv(path)
        return {
            "columns": list(df.columns),
            "row_count": len(df),
            "error": None,
        }
    except Exception as e:
        return {"columns": [], "row_count": 0, "error": str(e)}
