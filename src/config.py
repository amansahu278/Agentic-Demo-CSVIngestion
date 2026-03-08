"""Load config (mandatory columns, paths, LLM settings)."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Load .env once at import so OPENAI_API_KEY etc. are available
load_dotenv()

# Base paths: project root is parent of src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
INCOMING_DIR = DATA_DIR / "incoming"
ACCEPTED_DIR = DATA_DIR / "accepted"
REJECTED_DIR = DATA_DIR / "rejected"
NEEDS_REVIEW_DIR = DATA_DIR / "needs_review"
REPORTS_DIR = DATA_DIR / "reports"

CONFIG_DIR = PROJECT_ROOT / "config"
MANDATORY_COLUMNS_PATH = CONFIG_DIR / "mandatory_columns.yaml"
SETTINGS_PATH = CONFIG_DIR / "settings.yaml"


def load_mandatory_columns(path: Path | None = None) -> list[str]:
    """Load list of mandatory column names from YAML."""
    path = path or MANDATORY_COLUMNS_PATH
    with path.open() as f:
        data = yaml.safe_load(f)
    return list(data.get("mandatory_columns", []))


def _load_settings() -> dict:
    """Load settings.yaml; return empty dict if missing."""
    if not SETTINGS_PATH.exists():
        return {}
    with SETTINGS_PATH.open() as f:
        return yaml.safe_load(f) or {}


def get_openai_model() -> str:
    """OpenAI model name: from config/settings.yaml, overridden by OPENAI_MODEL env."""
    settings = _load_settings()
    default = settings.get("openai_model", "gpt-4o-mini")
    return os.environ.get("OPENAI_MODEL", default)


def get_openai_api_key() -> str | None:
    """OpenAI API key from environment (after dotenv load)."""
    return os.environ.get("OPENAI_API_KEY")
