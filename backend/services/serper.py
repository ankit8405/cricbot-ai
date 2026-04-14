from datetime import datetime
import json
from config import SERPER_API_KEY, SERPER_URL, http_client, redis_client
from core.text_processing import normalize_query_for_cache

def extract_serper_context(payload: dict) -> str:
    snippets: list[str] = []

    if isinstance(payload.get("answerBox"), dict):
        answer_box = payload["answerBox"]
        for key in ["answer", "snippet", "title"]:
            val = answer_box.get(key)
            if isinstance(val, str) and val.strip():
                snippets.append(val.strip())

    if isinstance(payload.get("knowledgeGraph"), dict):
        kg = payload["knowledgeGraph"]
        for key in ["title", "description"]:
            val = kg.get(key)
            if isinstance(val, str) and val.strip():
                snippets.append(val.strip())

    organic = payload.get("organic", [])
    if isinstance(organic, list):
        for item in organic[:4]:
            if not isinstance(item, dict):
                continue
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")
            joined = " - ".join(part for part in [title, snippet, link] if isinstance(part, str) and part.strip())
            if joined:
                snippets.append(joined)

    deduped: list[str] = []
    seen: set[str] = set()
    for s in snippets:
        compact = " ".join(s.split())
        key = compact.lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(compact)

    if not deduped:
        return ""

    context = "\n".join(f"- {line}" for line in deduped[:6])
    return context[:2200]

async def call_serper_raw(query: str) -> dict:
    if not SERPER_API_KEY:
        return {}

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": 4}

    try:
        resp = await http_client.post(SERPER_URL, headers=headers, json=payload)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}

async def get_serper_raw_cached(query: str) -> dict:
    cache_key = f"serper:raw:v1:{normalize_query_for_cache(query)}"

    if redis_client is not None:
        cached_payload = redis_client.get(cache_key)
        if isinstance(cached_payload, str) and cached_payload.strip():
            try:
                parsed = json.loads(cached_payload)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

    payload = await call_serper_raw(query)

    if redis_client is not None and payload:
        try:
            redis_client.set(cache_key, json.dumps(payload), ex=1800)
        except Exception:
            pass

    return payload

def build_intent_serper_query(user_msg: str, intent: str) -> str:
    base = user_msg
    year = datetime.now().year

    if intent == "player_stats":
        return f"{base} cricket stats runs average strike rate site:espncricinfo.com OR site:cricbuzz.com {year}"
    if intent == "comparison":
        return f"{base} comparison stats runs average strike rate site:espncricinfo.com OR site:cricbuzz.com {year}"
    if intent == "live_score":
        return f"{base} live cricket score today site:espncricinfo.com OR site:cricbuzz.com {year}"
    if intent == "match_result":
        return f"{base} latest match result cricket scorecard site:espncricinfo.com OR site:cricbuzz.com {year}"
    if intent == "standings":
        return f"{base} points table latest standings cricket {year} site:iplt20.com OR site:espncricinfo.com"
    return f"{base} cricket stats latest {year} site:espncricinfo.com OR site:cricbuzz.com"