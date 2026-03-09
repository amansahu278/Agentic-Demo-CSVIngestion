"""Configure logging to terminal and a file. Logs each graph step's return value."""
import logging
import sys
from pathlib import Path

# Project root (parent of src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOGS_DIR / "ingestion.log"

INGESTION_LOGGER = "ingestion"


def setup_logging(
    level: int | None = None,
    log_file: Path | None = None,
    *,
    debug: bool = False,
) -> None:
    """Configure the ingestion logger to write to terminal and file."""
    if level is None:
        level = logging.DEBUG if debug else logging.INFO
    log_file = log_file or LOG_FILE
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(INGESTION_LOGGER)
    logger.setLevel(level)
    # Avoid adding handlers twice if setup is called multiple times
    if logger.handlers:
        return

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)


def get_logger() -> logging.Logger:
    """Return the ingestion logger. Call setup_logging() first (e.g. in run_graph)."""
    return logging.getLogger(INGESTION_LOGGER)
