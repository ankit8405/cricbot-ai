import json
import re
from config import LLM_MODEL, FORMAT_TYPES, INTENTS, redis_client
from services.llm import call_groq_llm
from core.text_processing import normalize_query_for_cache

def classify_query_rules(query: str) -> str | None:
    q = query.lower()
    is_match_query = bool(re.search(r"\bvs\b|\bv\b", q))

    live_keywords = {"live", "current", "today", "ongoing", "score now", "live score"}
    result_keywords = {"last match", "previous match", "yesterday", "result", "who won", "won"}
    standings_keywords = {"points table", "standings", "table", "position"}
    stats_keywords = {
        "stats", "record", "runs", "average", "strike rate", "economy",
        "wickets", "century", "half century", "highest", "lowest",
    }
    comparison_keywords = {"who is better", "better", "compare", "comparison", "versus"}

    if any(k in q for k in live_keywords) and ("score" in q or is_match_query):
        return "live_score"
    if any(k in q for k in result_keywords):
        return "match_result"
    if any(k in q for k in standings_keywords) and "ipl" in q:
        return "standings"
    if any(k in q for k in stats_keywords):
        return "player_stats"
    if is_match_query and any(k in q for k in {"score", "result", "head to head", "h2h"}):
        return "match_result"
    if any(k in q for k in comparison_keywords):
        return "comparison"

    explanation_keywords = {"what is", "explain", "how does", "rules", "meaning"}
    if any(k in q for k in explanation_keywords):
        return "general"

    return None

async def classify_query_llm(query: str) -> str:
    prompt = f"""
Classify this cricket query into EXACTLY one type:
- player_stats
- live_score
- match_result
- standings
- comparison
- general

Guidance:
- player_stats: runs, wickets, averages, strike rate, records, career numbers.
- live_score: live/ongoing/current score requests.
- match_result: who won, previous/last match result, yesterday result.
- standings: points table or team positions in tournament.
- comparison: who is better / compare players or teams.
- general: rules, meaning, explanation, tactics, non-factual discussion.

Return ONLY strict one-line JSON:
{{"type":"<one_of_the_types_above>"}}

Query: {query}
"""

    raw = await call_groq_llm(prompt, LLM_MODEL, temperature=0.0)
    if raw:
        text = raw.strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                val = str(parsed.get("type", "")).strip().lower()
                if val in INTENTS:
                    return val
        except Exception:
            pass

        lowered = text.lower()
        for intent in INTENTS:
            if re.search(rf'"type"\s*:\s*"{re.escape(intent)}"', lowered):
                return intent
        if "stand" in lowered or "points table" in lowered:
            return "standings"
        if "live" in lowered:
            return "live_score"
        if "result" in lowered or "won" in lowered:
            return "match_result"
        if "compare" in lowered or "better" in lowered:
            return "comparison"
        if "stats" in lowered or "record" in lowered:
            return "player_stats"

    return "general"

async def smart_classifier(query: str) -> str:
    cache_key = f"classify:v2:{normalize_query_for_cache(query)}"

    if redis_client is not None:
        cached = redis_client.get(cache_key)
        if isinstance(cached, str) and cached in INTENTS:
            return cached

    short_tokens = len(query.split())
    if short_tokens <= 2:
        q = query.lower()
        if any(k in q for k in {"stats", "runs", "wickets", "record", "average"}):
            result = "player_stats"
        elif any(k in q for k in {"score", "live"}):
            result = "live_score"
        elif any(k in q for k in {"result", "won"}):
            result = "match_result"
        elif any(k in q for k in {"standings", "table"}):
            result = "standings"
        else:
            result = "general"
        if redis_client is not None:
            redis_client.set(cache_key, result, ex=3600)
        return result

    result = await classify_query_llm(query)

    if redis_client is not None:
        redis_client.set(cache_key, result, ex=3600)

    return result

def detect_format_rules(query: str) -> str | None:
    q = query.lower()

    if " vs " in q or "compare" in q or "comparison" in q or "better" in q:
        return "comparison"
    if any(word in q for word in ["wickets", "economy", "bowling", "maidens", "five wicket", "5w"]):
        return "player_bowling"
    if any(word in q for word in ["runs", "average", "strike rate", "century", "fifty", "batting"]):
        return "player_batting"
    if any(word in q for word in ["team", "points table", "standings", "rank", "wins", "losses"]):
        return "team_stats"
    if any(word in q for word in ["score", "match", "live", "result", "scorecard"]):
        return "match_score"
    if any(word in q for word in ["what is", "explain", "how", "rules", "meaning"]):
        return "general"
    return None

async def detect_format_llm(query: str) -> str:
    prompt = f"""
Classify this cricket query into ONE label:
- player_batting
- player_bowling
- team_stats
- match_score
- comparison
- general

Return ONLY the label text and nothing else.

Query: {query}
"""

    raw = await call_groq_llm(prompt, LLM_MODEL, temperature=0.0)
    if not raw:
        return "general"

    text = raw.strip().lower()
    for label in FORMAT_TYPES:
        if label == text:
            return label

    for label in FORMAT_TYPES:
        if label in text:
            return label

    return "general"

async def detect_format(query: str) -> str:
    cache_key = f"format:v1:{normalize_query_for_cache(query)}"

    if redis_client is not None:
        cached = redis_client.get(cache_key)
        if isinstance(cached, str) and cached in FORMAT_TYPES:
            return cached

    rule_result = detect_format_rules(query)
    if rule_result in FORMAT_TYPES:
        result = rule_result
    else:
        result = await detect_format_llm(query)

    if redis_client is not None:
        redis_client.set(cache_key, result, ex=3600)

    return result