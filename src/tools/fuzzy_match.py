"""Suggest mapping from actual column names to mandatory names using fuzzy matching."""
from rapidfuzz import fuzz
from rapidfuzz.process import extractOne

# Default threshold: 0–100 (rapidfuzz score). 85 = "close enough".
DEFAULT_THRESHOLD = 85


def fuzzy_match_columns(
    actual_columns: list[str],
    mandatory_columns: list[str],
    threshold: int | float = DEFAULT_THRESHOLD,
) -> dict:
    """
    For each mandatory column, find the best matching actual column (if above threshold).
    Returns dict with:
      - mapping: {actual_col: mandatory_col} for accepted matches
      - all_mandatory_matched: bool
      - unmatched_mandatory: list of mandatory columns with no good match
    """
    actual = [c.strip() for c in actual_columns]
    mandatory = [m.strip() for m in mandatory_columns]
    mapping = {}
    unmatched = []

    for mand in mandatory:
        if mand in actual:
            mapping[mand] = mand
            continue
        result = extractOne(mand, actual, scorer=fuzz.ratio)
        if result and result[1] >= threshold:
            mapping[result[0]] = mand
        else:
            unmatched.append(mand)

    return {
        "mapping": mapping,
        "all_mandatory_matched": len(unmatched) == 0,
        "unmatched_mandatory": unmatched,
    }
