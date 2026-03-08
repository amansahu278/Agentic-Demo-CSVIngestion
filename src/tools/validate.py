"""Validate that mandatory columns are present (strict, no fuzzy)."""


def validate_columns(actual_columns: list[str], mandatory_columns: list[str]) -> dict:
    """
    Check if all mandatory columns are present in actual_columns.
    Returns dict with keys: valid (bool), missing (list of mandatory names not found).
    """
    actual_set = {c.strip() for c in actual_columns}
    mandatory = [m.strip() for m in mandatory_columns]
    missing = [m for m in mandatory if m not in actual_set]
    return {"valid": len(missing) == 0, "missing": missing}
