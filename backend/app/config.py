"""Runtime configuration, loaded from backend/.env.

No hardcoded fallbacks — required vars must be present in the environment;
a missing one raises a clear error (try/except, no silent defaults).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

try:
    DATABASE_URL = os.environ["DATABASE_URL"]
    OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
    OPENROUTER_MODEL = os.environ["OPENROUTER_MODEL"]
except KeyError as exc:
    raise RuntimeError(
        f"Missing required env var {exc} (looked in {ENV_PATH}). "
        "Required: DATABASE_URL, OPENROUTER_API_KEY, OPENROUTER_MODEL."
    ) from exc
