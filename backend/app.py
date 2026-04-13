
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis
import httpx
import os
import uvicorn
import json
import re
from rapidfuzz import fuzz
from dotenv import load_dotenv

load_dotenv()

def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value.strip()


def normalize_host(value: str) -> str:
    host = value.strip().lower()
    host = host.replace("https://", "").replace("http://", "")
    return host.rstrip("/")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str

class ErrorResponse(BaseModel):
    error: str

# Chatbot Logic

redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
try:
    redis_client.ping()
except Exception:
    redis_client = None

CRICKETDATA_API_KEY = require_env("CRICKETDATA_API_KEY")
RAPIDAPI_KEY = require_env("RAPIDAPI_KEY")
HUGGINGFACE_API_KEY = require_env("HUGGINGFACE_API_KEY")

# API URLs
CRICKETDATA_BASE_URL = require_env("CRICKETDATA_BASE_URL").rstrip("/")
RAPIDAPI_BASE_URL = require_env("RAPIDAPI_BASE_URL").rstrip("/")
HUGGINGFACE_URL = require_env("HUGGINGFACE_URL")
RAPIDAPI_HOST = normalize_host(require_env("RAPIDAPI_HOST"))

greetings = {"hi", "hello", "hey", "hii", "heyy"}

knowledge_base = {
    "what is your name": "I'm CricBOTai, your virtual assistant!",
    "who made you": "I was developed by Ankit, a Computer Science Student",
    "who developed you": "I was developed by Ankit, a Computer Science Student",
    "how can you help me": "I can answer your questions, offer support, and more on cricket!",
    "what can you do": "I can answer your questions, offer support, and more on cricket!",
    "how are you useful": "I can answer your questions, offer support, and more on cricket!"
}

PLAYER_ALIASES = {
    "kohli": "Virat Kohli",
    "virat": "Virat Kohli",
    "rohit": "Rohit Sharma",
    "bumrah": "Jasprit Bumrah",
    "dhoni": "MS Dhoni",
    "hardik": "Hardik Pandya",
    "gill": "Shubman Gill"
}

TEAM_ALIASES = {
    "ipl": {
        "mi": ["mi", "mumbai indians"],
        "rcb": ["rcb", "bangalore", "royal challengers", "royal challengers bangalore"],
        "csk": ["csk", "chennai super kings"],
        "kkr": ["kkr", "kolkata knight riders"],
        "srh": ["srh", "sunrisers hyderabad"],
        "dc": ["dc", "delhi capitals"],
        "rr": ["rr", "rajasthan royals"],
        "pbks": ["pbks", "punjab kings", "kxip"],
        "gt": ["gt", "gujarat titans"],
        "lsg": ["lsg", "lucknow super giants"]
    },
    "international": {
        "india": ["india", "ind"],
        "australia": ["australia", "aus"],
        "england": ["england", "eng"],
        "pakistan": ["pakistan", "pak"],
        "south_africa": ["south africa", "sa"],
        "new_zealand": ["new zealand", "nz"]
    },
    "domestic": {
        "mumbai": ["mumbai"],
        "karnataka": ["karnataka"],
        "delhi": ["delhi"]
    }
}

def extract_player_name(query):
    lower_q = query.lower()
    if not any(word in lower_q for word in ["stats", "average", "runs", "wickets", "strike rate", "economy"]):
        return None
    for key, name in PLAYER_ALIASES.items():
        if key in lower_q:
            return name
    match = re.search(r"([A-Za-z]+\s+[A-Za-z]+)", query)
    if match and len(match.group(1).split()) == 2:
        first, second = match.group(1).lower().split()
        blocked = {"match", "today", "score", "stats", "runs", "live", "team", "vs", "of"}
        if first not in blocked and second not in blocked:
            return match.group(1)
    return None

async def llm_extract_player_name(query):
    prompt = f"""
Extract only the cricket player full name from this query.

Rules:
- Return JSON only in format: {{"player_name": "<name or empty>"}}
- If no player name is present, return an empty string.
- Do not guess.

Query: {query}
"""
    result = await call_huggingface_llm(prompt)
    if not result:
        return None

    try:
        match = re.search(r"\{.*\}", result, re.DOTALL)
        if not match:
            return None
        parsed = json.loads(match.group())
        player_name = parsed.get("player_name", "") if isinstance(parsed, dict) else ""
        player_name = player_name.strip() if isinstance(player_name, str) else ""
        if not player_name:
            return None

        if not re.fullmatch(r"[A-Za-z ]+", player_name):
            return None
        words = [w for w in player_name.split() if w]
        if len(words) < 1 or len(words) > 3:
            return None

        query_lower = query.lower()
        name_lower = player_name.lower()

        if re.search(rf"\b{re.escape(name_lower)}\b", query_lower):
            return player_name
        if fuzz.partial_ratio(name_lower, query_lower) >= 90:
            return player_name

        return None
    except Exception:
        return None

async def extract_player_name_full(query):
    name = extract_player_name(query)
    if name:
        return name
    return await llm_extract_player_name(query)

def detect_team_codes(query, competition):
    haystack = query.lower()
    found = set()
    league_map = TEAM_ALIASES.get(competition, {})

    for team_code, aliases in league_map.items():
        for alias in aliases:
            alias_l = alias.lower()
            if re.search(rf"\b{re.escape(alias_l)}\b", haystack):
                found.add(team_code)
                break
            threshold = 95 if len(alias_l) <= 3 else 85
            if fuzz.partial_ratio(alias_l, haystack) >= threshold:
                found.add(team_code)
                break

    return list(found)

async def llm_extract_team_codes(query, competition):
    league_map = TEAM_ALIASES.get(competition, {})
    if not league_map:
        return []

    aliases = []
    for code, names in league_map.items():
        aliases.append(f"{code}: {', '.join(names)}")

    prompt = f"""
Extract ONLY team codes from the list below.

Rules:
- Only return valid team codes.
- Do not guess.
- Return JSON array only.

Competition: {competition}
Teams:
{chr(10).join(aliases)}

Query: {query}
"""
    result = await call_huggingface_llm(prompt)
    if not result:
        return []

    try:
        array_match = re.search(r"\[.*\]", result, re.DOTALL)
        if not array_match:
            return []
        parsed = json.loads(array_match.group())
        if not isinstance(parsed, list):
            return []

        valid_codes = set(league_map.keys())
        return [code for code in parsed if isinstance(code, str) and code in valid_codes]
    except Exception:
        return []


async def extract_teams(query, competition):
    teams = detect_team_codes(query, competition)
    if teams:
        return teams
    return await llm_extract_team_codes(query, competition)


def detect_competition_from_query(query):
    query_lower = query.lower()
    if any(word in query_lower for word in ["ipl", "mi", "rcb", "csk", "kkr", "srh", "dc", "rr", "pbks", "gt", "lsg"]):
        return "ipl"
    if any(word in query_lower for word in ["india", "australia", "england", "pakistan", "new zealand", "south africa"]):
        return "international"
    if any(word in query_lower for word in ["ranji", "domestic", "smat", "vijay hazare", "karnataka", "mumbai", "delhi"]):
        return "domestic"

    return "unknown"

def team_code_matches_haystack(team_code, haystack, competition):
    aliases = TEAM_ALIASES.get(competition, {}).get(team_code, [team_code])
    for alias in aliases:
        if re.search(rf"\b{re.escape(alias.lower())}\b", haystack):
            return True
    return False

async def extract_relevant_api_payload(intent, query, payload, competition):
    if intent != "live_score" or not isinstance(payload, dict):
        return payload

    matches = payload.get("data") or payload.get("matches") or []
    if not isinstance(matches, list) or not matches:
        return payload

    query_teams = await extract_teams(query, competition)

    if not query_teams:
        top = matches[0] if isinstance(matches[0], dict) else {}
        return {
            "data": [
                {
                    "name": top.get("name"),
                    "status": top.get("status"),
                    "venue": top.get("venue"),
                    "date": top.get("date")
                }
            ]
        }

    filtered = []
    for item in matches:
        if not isinstance(item, dict):
            continue
        haystack = " ".join([
            str(item.get("name", "")),
            str(item.get("status", "")),
            str(item.get("venue", "")),
            json.dumps(item.get("teamInfo", ""))
        ]).lower()
        if all(team_code_matches_haystack(team, haystack, competition) for team in query_teams):
            filtered.append(
                {
                    "name": item.get("name"),
                    "status": item.get("status"),
                    "venue": item.get("venue"),
                    "date": item.get("date")
                }
            )

    if filtered:
        return {"data": filtered[:2]}

    return payload

async def resolve_player_id(query):
    player_name = await extract_player_name_full(query)
    if not player_name:
        return None

    url = f"{CRICKETDATA_BASE_URL}/players"
    params = {"apikey": CRICKETDATA_API_KEY, "offset": 0, "search": player_name}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for _ in range(2):
                try:
                    resp = await client.get(url, params=params)
                    if resp.status_code != 200:
                        continue
                    payload = resp.json()
                    players = payload.get("data", []) if isinstance(payload, dict) else []
                    if not players:
                        return None
                    first = players[0] if isinstance(players[0], dict) else {}
                    return first.get("id")
                except Exception:
                    continue
        return None
    except Exception:
        return None

async def call_cricketdata_api(intent, query=None, competition="ipl"):
    route_by_intent = {
        "live_score": "currentMatches",
        "schedule": "series",
        "player_stats": "players_info",
        "general": "currentMatches"
    }
    endpoint = route_by_intent.get(intent)
    if not endpoint:
        return None

    if competition == "domestic":
        return None

    url = f"{CRICKETDATA_BASE_URL}/{endpoint}"
    params = {"apikey": CRICKETDATA_API_KEY}

    if intent == "player_stats":
        player_id = await resolve_player_id(query or "")
        if not player_id:
            return {"error": "player_id_not_found"}
        params["id"] = player_id

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for _ in range(2):
                try:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        return resp.json()
                except Exception:
                    continue
        return None
    except Exception:
        return None

async def call_rapidapi_cricket(intent, competition="ipl"):
    route_by_intent = {
        # Free Cricbuzz API style endpoints
        "live_score": "cricket-match-live-list",
        "schedule": "cricket-series",
        "player_stats": "cricket-all-teams",
        "general": "cricket-match-live-list",
    }
    endpoint = route_by_intent.get(intent, "cricket-match-live-list")
    if competition == "domestic":
        return None
    url = f"{RAPIDAPI_BASE_URL}/{endpoint}"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for _ in range(2):
                try:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        return resp.json()
                except Exception:
                    continue
        return None
    except Exception:
        return None


async def fetch_ipl_data(intent, query):
    data = await call_cricketdata_api(intent, query, "ipl")
    if not data:
        data = await call_rapidapi_cricket(intent, "ipl")
    return data


async def fetch_international_data(intent, query):
    data = await call_cricketdata_api(intent, query, "international")
    if not data:
        data = await call_rapidapi_cricket(intent, "international")
    return data


async def fetch_domestic_data(intent, query):
    _ = intent
    _ = query
    return None

async def call_huggingface_llm(prompt):
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    payload = {"inputs": prompt}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(HUGGINGFACE_URL, headers=headers, json=payload)
        if resp.status_code == 200:
            result = resp.json()
            # HuggingFace returns a list of dicts with 'generated_text'
            if isinstance(result, list) and 'generated_text' in result[0]:
                return result[0]['generated_text']
            elif isinstance(result, dict) and 'generated_text' in result:
                return result['generated_text']
            else:
                return str(result)
        else:
            return None
    except Exception:
        return None

async def smart_guardrail(query):
    prompt = f"""
ONLY return valid JSON. No extra text.

Format:
{{
  "domain": "cricket|non-cricket",
  "type": "static|dynamic",
  "intent": "live_score|player_stats|schedule|general",
    "competition": "ipl|international|domestic|unknown",
  "safe": true
}}

Query: {query}
"""
    result = await call_huggingface_llm(prompt)
    if not result:
        return {"domain": "non-cricket", "type": "static", "intent": "general", "competition": "unknown", "safe": True}

    try:
        match = re.search(r"\{.*\}", result, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in LLM output")

        decision = json.loads(match.group())
        return {
            "domain": decision.get("domain", "cricket"),
            "type": decision.get("type", "static"),
            "intent": decision.get("intent", "general"),
            "competition": decision.get("competition", "unknown"),
            "safe": bool(decision.get("safe", True))
        }
    except Exception:
        return {"domain": "non-cricket", "type": "static", "intent": "general", "competition": "unknown", "safe": True}

async def generate_llm_answer(prompt):
    result = await call_huggingface_llm(prompt)
    return result or "I'm having trouble generating a response right now."

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    user_msg = request.message.strip()
    if not user_msg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No message provided"
        )

    user_msg_lower = user_msg.lower()
    print("User:", user_msg)

    if user_msg_lower in greetings:
        return ChatResponse(reply="Hey there! How can I assist you today?")
    if user_msg_lower in knowledge_base:
        return ChatResponse(reply=knowledge_base[user_msg_lower])

    detected_competition = detect_competition_from_query(user_msg)

    if any(word in user_msg_lower for word in ["score", "match", "today", "won"]):
        decision = {
            "domain": "cricket",
            "type": "dynamic",
            "intent": "live_score",
            "competition": detected_competition,
            "safe": True
        }
    elif any(word in user_msg_lower for word in ["average", "stats", "runs", "wickets", "strike rate", "economy"]):
        decision = {
            "domain": "cricket",
            "type": "dynamic",
            "intent": "player_stats",
            "competition": detected_competition,
            "safe": True
        }
    else:
        decision = await smart_guardrail(user_msg)
        if decision.get("competition") == "unknown" and detected_competition != "unknown":
            decision["competition"] = detected_competition

    print("Decision:", decision)

    if not decision.get("safe", True):
        return ChatResponse(reply="Sorry, your query is not appropriate.")
    if decision.get("domain") != "cricket":
        return ChatResponse(reply="Only cricket queries are allowed.")

    normalized_query = re.sub(r"\s+", " ", user_msg_lower).strip()
    intent = decision.get("intent", "general")
    competition = decision.get("competition", "unknown")
    cache_key = f"cric:{competition}:{intent}:{normalized_query}"
    if redis_client is not None:
        cached = redis_client.get(cache_key)
        if cached:
            return ChatResponse(reply=cached)

    if decision.get("type") == "static":
        reply = await generate_llm_answer(user_msg)
        if redis_client is not None:
            redis_client.set(cache_key, reply, ex=3600)
        return ChatResponse(reply=reply)

    if decision.get("type") == "dynamic":
        if competition == "ipl":
            data = await fetch_ipl_data(decision.get("intent"), user_msg)
        elif competition == "international":
            data = await fetch_international_data(decision.get("intent"), user_msg)
        elif competition == "domestic":
            data = await fetch_domestic_data(decision.get("intent"), user_msg)
        else:
            data = await call_cricketdata_api(decision.get("intent"), user_msg, "ipl")

        if isinstance(data, dict) and data.get("error") == "player_id_not_found":
            return ChatResponse(reply="I could not identify the player. Please include full player name, for example: Virat Kohli.")

        if data:
            payload_competition = competition if competition in {"ipl", "international", "domestic"} else "ipl"
            relevant_data = await extract_relevant_api_payload(decision.get("intent"), user_msg, data, payload_competition)
            if decision.get("intent") == "live_score" and isinstance(relevant_data, dict):
                summary_lines = []
                for match in relevant_data.get("data", []):
                    if isinstance(match, dict):
                        name = match.get("name", "Unknown match")
                        status = match.get("status", "Status unavailable")
                        summary_lines.append(f"{name} - {status}")
                compact_data = "\n".join(summary_lines)[:1000] if summary_lines else json.dumps(relevant_data)[:1000]
            elif decision.get("intent") == "player_stats" and isinstance(relevant_data, dict):
                player_block = relevant_data
                if isinstance(relevant_data.get("data"), dict):
                    player_block = relevant_data.get("data")
                elif isinstance(relevant_data.get("data"), list) and relevant_data.get("data"):
                    first_item = relevant_data.get("data")[0]
                    player_block = first_item if isinstance(first_item, dict) else relevant_data

                name = player_block.get("name", "Player") if isinstance(player_block, dict) else "Player"
                runs = (
                    player_block.get("runs") or player_block.get("totalRuns") or "N/A"
                ) if isinstance(player_block, dict) else "N/A"
                match_count = player_block.get("matches", "N/A") if isinstance(player_block, dict) else "N/A"
                direct_reply = f"{name}: Runs {runs}, Matches {match_count}."
                if redis_client is not None:
                    redis_client.set(cache_key, direct_reply, ex=3600)
                return ChatResponse(reply=direct_reply)
            else:
                compact_data = json.dumps(relevant_data)[:1000]
            llm_input = f"""
You are a professional cricket analyst. Answer using ONLY the provided data. Do not guess.

User question: {user_msg}

Use ONLY the data below:
{compact_data}

Give a clear, concise, and fact-based answer in 1-2 sentences.
"""
            reply = await generate_llm_answer(llm_input)
            if redis_client is not None:
                redis_client.set(cache_key, reply, ex=3600)
            return ChatResponse(reply=reply)
        else:
            if competition == "domestic":
                return ChatResponse(reply="Domestic live routing is limited right now. Please try an IPL or international query, or rephrase with more detail.")
            return ChatResponse(reply="Live match data is unavailable right now. Please try again in a moment.")

    return ChatResponse(reply="Hmm, I don't have an answer for that yet 🤔. You can try rephrasing or ask something else!")

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
