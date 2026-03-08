"""Rename CSV columns using a mapping (actual_name -> mandatory_name) and write to disk."""
from pathlib import Path

import pandas as pd


def normalize_csv_columns(
    file_path: str | Path,
    column_mapping: dict[str, str],
    output_path: str | Path | None = None,
) -> dict:
    """
    Read CSV, rename columns by mapping (only renames keys that exist), write to output_path.
    If output_path is None, overwrites the original file.
    Returns dict with: output_path, error (if any).
    """
    path = Path(file_path)
    out = Path(output_path) if output_path else path
    try:
        df = pd.read_csv(path)
        # Only rename columns that exist in the dataframe
        rename = {k: v for k, v in column_mapping.items() if k in df.columns}
        df = df.rename(columns=rename)
        df.to_csv(out, index=False)
        return {"output_path": str(out), "error": None}
    except Exception as e:
        return {"output_path": None, "error": str(e)}
