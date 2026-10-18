"""Application configuration from the environment."""
from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "SignalX Research contact@example.com").strip()
MAX_SEARCH_RESULTS = 7
MAX_PAGE_CHARS = 24_000
REQUEST_TIMEOUT = 18
HISTORY_PATH = ROOT / "data" / "history.json"
