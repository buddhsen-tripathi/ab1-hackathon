import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

BASE_URL = "https://hackathon.prod.pulsefoundry.ai"
FACILITY_IDS = [101, 102, 103]

DATA_DIR = _PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "billready.db"
OUTPUT_CSV = DATA_DIR / "eligibility.csv"

MAX_CONCURRENT_REQUESTS = 12
MAX_RETRIES = 12

# LLM copilot runs after rules-based routing on Needs Review cases only
LLM_MODEL = "gpt-4o-mini"
LLM_CHUNK_SIZE = 5  # patients per API call (~17 calls for ~85 review cases)

REQUIRED_WOUND_FIELDS = (
    "wound_type",
    "length_cm",
    "width_cm",
    "depth_cm",
    "drainage_amount",
)


def openai_api_key() -> str | None:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    return key or None


def llm_unavailable_reason() -> str | None:
    """Why LLM is off, or None if ready."""
    if not openai_api_key():
        return "missing_key"
    try:
        import openai  # noqa: F401
    except ImportError:
        return "missing_package"
    return None


def llm_available() -> bool:
    return llm_unavailable_reason() is None
