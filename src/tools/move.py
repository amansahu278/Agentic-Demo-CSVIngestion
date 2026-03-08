"""Move a file into one of the piles: accepted, rejected, needs_review."""
import shutil
from pathlib import Path

from src.config import ACCEPTED_DIR, REJECTED_DIR, NEEDS_REVIEW_DIR

PILES = {"accepted", "rejected", "needs_review"}
DIRS = {
    "accepted": ACCEPTED_DIR,
    "rejected": REJECTED_DIR,
    "needs_review": NEEDS_REVIEW_DIR,
}


def move_file_to_pile(
    file_path: str | Path,
    pile: str,
    *,
    accepted_dir: Path = ACCEPTED_DIR,
    rejected_dir: Path = REJECTED_DIR,
    needs_review_dir: Path = NEEDS_REVIEW_DIR,
) -> dict:
    """
    Copy or move the file into the given pile directory.
    Returns dict with: destination_path, error (if any).
    """
    if pile not in PILES:
        return {"destination_path": None, "error": f"Invalid pile: {pile}. Must be one of {PILES}"}
    path = Path(file_path)
    if not path.exists():
        return {"destination_path": None, "error": f"File not found: {path}"}
    dirs = {"accepted": accepted_dir, "rejected": rejected_dir, "needs_review": needs_review_dir}
    dest_dir = dirs[pile]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / path.name
    try:
        shutil.copy2(path, dest_path)
        return {"destination_path": str(dest_path), "error": None}
    except Exception as e:
        return {"destination_path": None, "error": str(e)}
