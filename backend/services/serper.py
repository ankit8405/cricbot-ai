import asyncio
from datetime import datetime
import json
import re
from config import SERPER_API_KEY, SERPER_URL, http_client, redis_client
from core.text_processing import normalize_query_for_cache


def detect_query_scope(query: str) -> tuple[str, str | None]:
    q = query.lower()

    year_match = re.search(r"(20\d{2})", q)
    if year_match:
        return "season", year_match.group(1)

    if "this season" in q or "current season" in q:
        return "season", "current"

    if any(x in q for x in ["today", "yesterday", "last match", "live"]):
        return "match", None

    return "career", None


def _line_matches_scope(line: str, scope: str, year: str | None) -> bool:
    l = line.lower()

    if scope == "career":
        if re.search(r"\b20\d{2}\b", l):
            return False
        if any(x in l for x in ["this season", "current season", "last match", "yesterday", "today", "live", "scorecard"]):
            return False
        return True

    if scope == "season":
        if year == "current":
            return any(x in l for x in ["this season", "current season", "season", "ipl 20"])
        if year:
            return year in l
        return "season" in l

    if scope == "match":
        return any(x in l for x in ["over", "overs", "runs", "won", "score", "scorecard", "wicket", "target", "chase", "result", "match", "live"])

    return True


def _scope_filter_lines(lines: list[str], query: str | None) -> list[str]:
    if not query:
        return lines

    scope, year = detect_query_scope(query)
    filtered = [line for line in lines if _line_matches_scope(line, scope, year)]
    return filtered or lines

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
    stat_like_terms = (
        "runs", "average", "avg", "strike rate", "sr", "wickets", "economy", "score", "result", "points",
    )
    filtered_snippets = 0
    if isinstance(organic, list):
        for item in organic[:6]:
            if not isinstance(item, dict):
                continue
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            if isinstance(snippet, str) and snippet.strip():
                if any(term in snippet.lower() for term in stat_like_terms):
                    filtered_snippets += 1
                else:
                    continue
            link = item.get("link", "")
            joined = " - ".join(part for part in [title, snippet, link] if isinstance(part, str) and part.strip())
            if joined:
                snippets.append(joined)

    if filtered_snippets == 0 and isinstance(organic, list):
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


def _all_candidate_lines(payload: dict) -> list[str]:
    lines: list[str] = []

    if isinstance(payload.get("answerBox"), dict):
        box = payload["answerBox"]
        for key in ["answer", "snippet", "title"]:
            val = box.get(key)
            if isinstance(val, str) and val.strip():
                lines.append(val.strip())

    if isinstance(payload.get("knowledgeGraph"), dict):
        kg = payload["knowledgeGraph"]
        for key in ["title", "description"]:
            val = kg.get(key)
            if isinstance(val, str) and val.strip():
                lines.append(val.strip())

    organic = payload.get("organic", [])
    if isinstance(organic, list):
        for item in organic[:8]:
            if not isinstance(item, dict):
                continue
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            joined = " - ".join(part for part in [title, snippet] if isinstance(part, str) and part.strip())
            if joined:
                lines.append(joined)

    deduped: list[str] = []
    seen: set[str] = set()
    for line in lines:
        compact = " ".join(line.split())
        key = compact.lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(compact)
    return deduped


def extract_stat_focused_context(payload: dict, max_lines: int = 8, query: str | None = None) -> str:
    stat_terms = (
        "runs", "matches", "average", "avg", "strike rate", "sr",
        "wickets", "economy", "score", "won", "points", "table",
    )
    base_lines = _scope_filter_lines(_all_candidate_lines(payload), query)
    lines = [line for line in base_lines if any(term in line.lower() for term in stat_terms)]
    if not lines:
        lines = base_lines
    return "\n".join(f"- {line}" for line in lines[:max_lines])[:2600]


def extract_structured_metrics(payload: dict, query: str | None = None) -> dict[str, str]:
    metrics: dict[str, str] = {
        "runs": "N/A",
        "matches": "N/A",
        "average": "N/A",
        "strike_rate": "N/A",
        "wickets": "N/A",
        "economy": "N/A",
    }

    lines = _scope_filter_lines(_all_candidate_lines(payload), query)
    if not lines:
        return metrics

    best_score = 0
    best_metrics = metrics.copy()

    for line in lines:
        lower = line.lower()
        temp = metrics.copy()
        score = 0

        m = re.search(r"(\d{3,5})\s+runs", lower)
        if m:
            temp["runs"] = m.group(1)
            score += 2
        else:
            m = re.search(r"runs\s*[:\-]?\s*(\d{3,5})", lower)
            if m:
                temp["runs"] = m.group(1)
                score += 2

        m = re.search(r"(\d{1,4})\s+matches", lower)
        if m:
            temp["matches"] = m.group(1)
            score += 1

        m = re.search(r"(?:average|avg)\s*[:\-]?\s*(\d{1,3}(?:\.\d+)?)", lower)
        if m:
            temp["average"] = m.group(1)
            score += 2

        m = re.search(r"(?:strike\s*rate|sr)\s*[:\-]?\s*(\d{1,3}(?:\.\d+)?)", lower)
        if m:
            temp["strike_rate"] = m.group(1)
            score += 2

        m = re.search(r"(\d{1,4})\s+wickets", lower)
        if m:
            temp["wickets"] = m.group(1)
            score += 2
        else:
            m = re.search(r"wickets\s*[:\-]?\s*(\d{1,4})", lower)
            if m:
                temp["wickets"] = m.group(1)
                score += 2

        m = re.search(r"economy\s*[:\-]?\s*(\d{1,2}(?:\.\d+)?)", lower)
        if m:
            temp["economy"] = m.group(1)
            score += 1

        if score > best_score:
            best_score = score
            best_metrics = temp

    return best_metrics


def has_any_metric(metrics: dict[str, str], fields: list[str]) -> bool:
    return any(metrics.get(field, "N/A") != "N/A" for field in fields)


def has_minimum_batting_metrics(metrics: dict[str, str]) -> bool:
    return metrics.get("runs", "N/A") != "N/A" and metrics.get("average", "N/A") != "N/A"


def has_minimum_bowling_metrics(metrics: dict[str, str]) -> bool:
    return metrics.get("wickets", "N/A") != "N/A" and metrics.get("economy", "N/A") != "N/A"


def build_player_stats_markdown(title: str, metrics: dict[str, str], bowling: bool = False) -> str:
    if bowling:
        return "\n".join(
            [
                "**Bowling Stats**",
                f"- Player: {title}",
                f"- Wickets: {metrics.get('wickets', 'N/A')}",
                f"- Matches: {metrics.get('matches', 'N/A')}",
                f"- Economy: {metrics.get('economy', 'N/A')}",
                f"- Average: {metrics.get('average', 'N/A')}",
                "",
                "**Notes**",
                "- Values are extracted from current sources; missing fields are marked N/A.",
            ]
        )

    return "\n".join(
        [
            "**Batting Stats**",
            f"- Player: {title}",
            f"- Runs: {metrics.get('runs', 'N/A')}",
            f"- Matches: {metrics.get('matches', 'N/A')}",
            f"- Average: {metrics.get('average', 'N/A')}",
            f"- Strike Rate: {metrics.get('strike_rate', 'N/A')}",
            "",
            "**Notes**",
            "- Values are extracted from current sources; missing fields are marked N/A.",
        ]
    )


def build_comparison_markdown(
    left_name: str,
    right_name: str,
    left_metrics: dict[str, str],
    right_metrics: dict[str, str],
) -> str:
    return "\n".join(
        [
            "**Comparison Table**",
            "",
            f"| Metric | {left_name} | {right_name} |",
            "|--------|----------|----------|",
            f"| Runs | {left_metrics.get('runs', 'N/A')} | {right_metrics.get('runs', 'N/A')} |",
            f"| Average | {left_metrics.get('average', 'N/A')} | {right_metrics.get('average', 'N/A')} |",
            f"| Strike Rate | {left_metrics.get('strike_rate', 'N/A')} | {right_metrics.get('strike_rate', 'N/A')} |",
            "",
            "**Summary**",
            "- Table values are extracted from current sources only.",
            "- Any missing metric is marked N/A due to incomplete source snippets.",
        ]
    )


def is_team_query(query: str) -> bool:
    q = query.lower()
    team_tokens = {
        "team", "squad", "mi", "rcb", "csk", "kkr", "srh", "dc", "rr", "pbks",
        "india", "australia", "england", "pakistan", "new zealand", "south africa",
    }
    return any(token in q for token in team_tokens)


def extract_team_metrics(payload: dict, query: str | None = None) -> dict[str, str]:
    metrics = {
        "matches": "N/A",
        "wins": "N/A",
        "losses": "N/A",
        "rank_points": "N/A",
    }

    lines = _scope_filter_lines(_all_candidate_lines(payload), query)
    for line in lines:
        lower = line.lower()

        if metrics["matches"] == "N/A":
            m = re.search(r"(\d{1,3})\s+matches", lower) or re.search(r"matches\s*[:\-]?\s*(\d{1,3})", lower)
            if m:
                metrics["matches"] = m.group(1)

        if metrics["wins"] == "N/A":
            m = re.search(r"(\d{1,3})\s+wins", lower) or re.search(r"wins\s*[:\-]?\s*(\d{1,3})", lower)
            if m:
                metrics["wins"] = m.group(1)

        if metrics["losses"] == "N/A":
            m = re.search(r"(\d{1,3})\s+losses", lower) or re.search(r"losses\s*[:\-]?\s*(\d{1,3})", lower)
            if m:
                metrics["losses"] = m.group(1)

        if metrics["rank_points"] == "N/A":
            m = re.search(r"(?:rank|position)\s*[:\-]?\s*(\d{1,2})", lower)
            if m:
                metrics["rank_points"] = f"Rank {m.group(1)}"
            else:
                m = re.search(r"points\s*[:\-]?\s*(\d{1,3})", lower)
                if m:
                    metrics["rank_points"] = f"Points {m.group(1)}"

    return metrics


def has_minimum_team_metrics(metrics: dict[str, str]) -> bool:
    has_core = metrics.get("matches", "N/A") != "N/A"
    has_support = any(metrics.get(k, "N/A") != "N/A" for k in ["wins", "losses", "rank_points"])
    return has_core and has_support


def build_team_markdown(title: str, metrics: dict[str, str]) -> str:
    return "\n".join(
        [
            "**Team Overview**",
            f"- Team/Context: {title}",
            f"- Matches: {metrics.get('matches', 'N/A')}",
            f"- Wins: {metrics.get('wins', 'N/A')}",
            f"- Losses: {metrics.get('losses', 'N/A')}",
            f"- Rank/Points: {metrics.get('rank_points', 'N/A')}",
            "",
            "**Key Points**",
            "- Values are extracted from current sources only.",
            "- Missing values are marked N/A.",
        ]
    )


def extract_match_info(payload: dict, query: str | None = None) -> dict[str, str]:
    result = {
        "summary": "N/A",
        "score": "N/A",
        "winner": "N/A",
    }

    lines = _scope_filter_lines(_all_candidate_lines(payload), query)
    for line in lines:
        lower = line.lower()
        if result["winner"] == "N/A":
            if "won by" in lower or lower.startswith("won"):
                result["winner"] = line
        if result["score"] == "N/A":
            if re.search(r"\d+\s*/\s*\d+", lower) or "score" in lower:
                result["score"] = line
        if result["summary"] == "N/A":
            if any(k in lower for k in ["match", "result", "won", "defeated", "beat"]):
                result["summary"] = line

    return result


def has_match_info(match_info: dict[str, str]) -> bool:
    return any(match_info.get(k, "N/A") != "N/A" for k in ["summary", "score", "winner"])


def build_match_markdown(title: str, info: dict[str, str]) -> str:
    return "\n".join(
        [
            "**Match Summary**",
            f"- Query: {title}",
            f"- Score: {info.get('score', 'N/A')}",
            f"- Result: {info.get('winner', 'N/A')}",
            "",
            "**Key Points**",
            f"- {info.get('summary', 'Match result not found in current sources.')}",
            "- Values are extracted from current sources only.",
        ]
    )

async def call_serper_raw(query: str) -> dict:
    if not SERPER_API_KEY:
        return {}

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": 8}

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
    scope = "ipl" if "ipl" in base.lower() else "cricket"
    query_scope, scope_year = detect_query_scope(user_msg)

    if query_scope == "season":
        season_year = str(datetime.now().year) if scope_year == "current" else (scope_year or str(year))
        if intent == "comparison":
            return (
                f"{base} {season_year} {scope} comparison batting stats runs average strike rate matches "
                f"site:espncricinfo.com OR site:cricbuzz.com"
            )
        return (
            f"{base} {season_year} {scope} batting stats runs average strike rate matches "
            f"site:espncricinfo.com OR site:cricbuzz.com"
        )

    if query_scope == "match":
        if intent == "live_score":
            return f"{base} live cricket score today site:espncricinfo.com OR site:cricbuzz.com {year}"
        return f"{base} latest cricket match score result scorecard site:espncricinfo.com OR site:cricbuzz.com {year}"

    if intent == "player_stats":
        return (
            f"{base} {scope} career batting stats runs average strike rate total runs "
            f"site:espncricinfo.com OR site:cricbuzz.com {year}"
        )
    if intent == "comparison":
        return (
            f"{base} {scope} comparison batting stats runs average strike rate total runs "
            f"site:espncricinfo.com OR site:cricbuzz.com {year}"
        )
    if intent == "live_score":
        return f"{base} live cricket score today site:espncricinfo.com OR site:cricbuzz.com {year}"
    if intent == "match_result":
        return f"{base} latest match result cricket scorecard site:espncricinfo.com OR site:cricbuzz.com {year}"
    if intent == "standings":
        return f"{base} points table latest standings cricket {year} site:iplt20.com OR site:espncricinfo.com"
    return f"{base} cricket stats latest {year} site:espncricinfo.com OR site:cricbuzz.com"


def build_entity_stats_query(entity: str, user_msg: str) -> str:
    year = datetime.now().year
    scope = "ipl" if "ipl" in user_msg.lower() else "cricket"
    query_scope, scope_year = detect_query_scope(user_msg)
    if query_scope == "season":
        season_year = str(datetime.now().year) if scope_year == "current" else (scope_year or str(year))
        return (
            f"{entity} {scope} {season_year} batting stats total runs matches average strike rate "
            f"site:espncricinfo.com OR site:cricbuzz.com"
        )
    if query_scope == "match":
        return (
            f"{entity} {scope} latest match score performance site:espncricinfo.com OR site:cricbuzz.com {year}"
        )
    return (
        f"{entity} {scope} career batting stats total runs matches average strike rate "
        f"site:espncricinfo.com OR site:cricbuzz.com {year}"
    )


def _merge_metrics(primary: dict[str, str], fallback: dict[str, str]) -> dict[str, str]:
    merged = dict(primary)
    for key, val in fallback.items():
        if merged.get(key, "N/A") == "N/A" and val != "N/A":
            merged[key] = val
    return merged


def _missing_batting_fields(metrics: dict[str, str]) -> list[str]:
    wanted = ["runs", "matches", "average", "strike_rate"]
    return [field for field in wanted if metrics.get(field, "N/A") == "N/A"]


def _metric_targeted_query(entity: str, user_msg: str, field: str) -> str:
    year = datetime.now().year
    scope = "ipl" if "ipl" in user_msg.lower() else "cricket"
    query_scope, scope_year = detect_query_scope(user_msg)
    mapping = {
        "runs": "total runs",
        "matches": "matches innings",
        "average": "batting average",
        "strike_rate": "strike rate",
    }
    metric_phrase = mapping.get(field, field)
    if query_scope == "season":
        season_year = str(datetime.now().year) if scope_year == "current" else (scope_year or str(year))
        return (
            f"{entity} {scope} {season_year} {metric_phrase} site:espncricinfo.com OR site:cricbuzz.com"
        )
    return (
        f"{entity} {scope} {metric_phrase} site:espncricinfo.com OR site:cricbuzz.com {year}"
    )


async def fetch_entity_metrics(entity: str, user_msg: str) -> tuple[dict[str, str], str]:
    base_query = build_entity_stats_query(entity, user_msg)
    base_payload = await get_serper_raw_cached(base_query)

    metrics = extract_structured_metrics(base_payload, user_msg) if isinstance(base_payload, dict) else {
        "runs": "N/A",
        "matches": "N/A",
        "average": "N/A",
        "strike_rate": "N/A",
        "wickets": "N/A",
        "economy": "N/A",
    }
    context = extract_stat_focused_context(base_payload, max_lines=8, query=user_msg) if isinstance(base_payload, dict) else ""

    missing = _missing_batting_fields(metrics)
    if missing:
        targeted_queries = [_metric_targeted_query(entity, user_msg, field) for field in missing]
        targeted_payloads = await asyncio.gather(
            *[get_serper_raw_cached(q) for q in targeted_queries],
            return_exceptions=True,
        )

        extra_chunks: list[str] = []
        for payload in targeted_payloads:
            if not isinstance(payload, dict):
                continue
            extracted = extract_structured_metrics(payload, user_msg)
            metrics = _merge_metrics(metrics, extracted)
            c = extract_stat_focused_context(payload, max_lines=4, query=user_msg)
            if c.strip():
                extra_chunks.append(c)

        if extra_chunks:
            context = "\n".join([context] + extra_chunks).strip()

    return metrics, context