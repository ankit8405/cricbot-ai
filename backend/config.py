import os
import httpx
import redis
from dotenv import load_dotenv

load_dotenv()

def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value.strip()

HTTP_TIMEOUT_SECONDS = 8.0
http_client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)

redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
try:
    redis_client.ping()
except Exception:
    redis_client = None

GROQ_API_KEY = require_env("GROQ_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "").strip()
SERPER_URL = "https://google.serper.dev/search"
LLM_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()

INTENTS = {
    "player_stats",
    "live_score",
    "match_result",
    "standings",
    "comparison",
    "general",
}

FORMAT_TYPES = {
    "player_batting",
    "player_bowling",
    "team_stats",
    "match_score",
    "comparison",
    "general",
}

CRICKET_KEYWORDS = {
    "cricket", "ipl", "odi", "t20", "test", "innings", "wicket", "wickets", "runs", "run rate",
    "strike rate", "batting", "bowling", "fielder", "captain", "series", "world cup", "bbl", "psl",
    "cpl", "ashes", "score", "scores", "match", "matches", "result", "won", "yesterday",
    "today", "live", "current", "powerplay", "boundary", "over", "overs", "century", "fifty",
}