import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config import FORMAT_TYPES, INTENTS, http_client, redis_client
from schemas import ChatRequest, ChatResponse
from services.llm import generate_llm_answer
from services.serper import (
    build_comparison_markdown,
    fetch_entity_metrics,
    build_match_markdown,
    build_team_markdown,
    build_intent_serper_query,
    build_player_stats_markdown,
    extract_match_info,
    extract_serper_context,
    extract_stat_focused_context,
    extract_structured_metrics,
    extract_team_metrics,
    get_serper_raw_cached,
    has_match_info,
    has_minimum_batting_metrics,
    has_minimum_bowling_metrics,
    has_minimum_team_metrics,
)
from core.prompts import (
    build_batting_prompt,
    build_bowling_prompt,
    build_comparison_prompt,
    build_formatter_prompt,
    build_match_prompt,
    build_prompt,
    build_team_prompt,
)
from core.classifier import classify_query_rules, detect_format, smart_classifier
from core.text_processing import (
    enforce_markdown_structure,
    extract_comparison_entities,
    is_cricket_query,
    is_valid_reply,
    normalize_query_for_cache,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await http_client.aclose()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    user_msg = request.message.strip()
    if not user_msg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No message provided",
        )
    
    if not is_cricket_query(user_msg):
        return ChatResponse(reply="I only answer cricket-related queries.")

    normalized_query = normalize_query_for_cache(user_msg)
    generic_cache_key = f"cric:v11:{normalized_query}"

    if redis_client is not None:
        cached = redis_client.get(generic_cache_key)
        if cached:
            return ChatResponse(reply=cached)

    rule_intent = classify_query_rules(user_msg)
    if rule_intent in INTENTS:
        query_type_task = asyncio.create_task(asyncio.sleep(0, result=rule_intent))
    else:
        query_type_task = asyncio.create_task(smart_classifier(user_msg))

    format_type_task = asyncio.create_task(detect_format(user_msg))

    query_type = await query_type_task
    detected = await format_type_task
    format_type = detected if isinstance(detected, str) and detected in FORMAT_TYPES else "general"
    cache_key = f"cric:v11:{query_type}:{format_type}:{normalized_query}"

    if redis_client is not None:
        cached = redis_client.get(cache_key)
        if cached:
            return ChatResponse(reply=cached)

    serper_query = build_intent_serper_query(user_msg, query_type)
    try:
        raw_payload = await asyncio.wait_for(get_serper_raw_cached(serper_query), timeout=2.0)
    except asyncio.TimeoutError:
        raw_payload = {}
    web_context = extract_serper_context(raw_payload) if raw_payload else ""
    structured_metrics = extract_structured_metrics(raw_payload, user_msg) if raw_payload else {}

    if format_type == "comparison":
        entities = extract_comparison_entities(user_msg)
        if entities:
            left, right = entities
            left_result, right_result = await asyncio.gather(
                fetch_entity_metrics(left, user_msg),
                fetch_entity_metrics(right, user_msg),
                return_exceptions=True,
            )

            left_metrics, left_context = left_result if isinstance(left_result, tuple) else ({}, "")
            right_metrics, right_context = right_result if isinstance(right_result, tuple) else ({}, "")

            if has_minimum_batting_metrics(left_metrics) and has_minimum_batting_metrics(right_metrics):
                reply = build_comparison_markdown(left, right, left_metrics, right_metrics)
                if redis_client is not None:
                    ttl = 900 if query_type in {"live_score", "match_result", "standings"} else 1800
                    redis_client.set(cache_key, reply, ex=ttl)
                    if query_type == "general":
                        redis_client.set(generic_cache_key, reply, ex=ttl)
                return ChatResponse(reply=reply)

            chunks: list[str] = []
            if web_context.strip():
                chunks.append("General context:\n" + web_context)
            if left_context.strip():
                chunks.append(f"{left}:\n{left_context}")
            if right_context.strip():
                chunks.append(f"{right}:\n{right_context}")
            if chunks:
                web_context = "\n\n".join(chunks)

    if format_type in {"player_batting", "player_bowling"}:
        can_use = has_minimum_bowling_metrics(structured_metrics) if format_type == "player_bowling" else has_minimum_batting_metrics(structured_metrics)
        if can_use:
            title = user_msg
            if format_type == "player_bowling":
                reply = build_player_stats_markdown(title, structured_metrics, bowling=True)
            else:
                reply = build_player_stats_markdown(title, structured_metrics, bowling=False)
            if redis_client is not None:
                ttl = 900 if query_type in {"live_score", "match_result", "standings"} else 1800
                redis_client.set(cache_key, reply, ex=ttl)
                if query_type == "general":
                    redis_client.set(generic_cache_key, reply, ex=ttl)
            return ChatResponse(reply=reply)

    if format_type == "team_stats":
        team_metrics = extract_team_metrics(raw_payload, user_msg) if raw_payload else {}
        if has_minimum_team_metrics(team_metrics):
            reply = build_team_markdown(user_msg, team_metrics)
            if redis_client is not None:
                ttl = 900 if query_type in {"live_score", "match_result", "standings"} else 1800
                redis_client.set(cache_key, reply, ex=ttl)
                if query_type == "general":
                    redis_client.set(generic_cache_key, reply, ex=ttl)
            return ChatResponse(reply=reply)

    if format_type == "match_score":
        match_info = extract_match_info(raw_payload, user_msg) if raw_payload else {}
        if has_match_info(match_info):
            reply = build_match_markdown(user_msg, match_info)
            if redis_client is not None:
                ttl = 900 if query_type in {"live_score", "match_result", "standings"} else 1800
                redis_client.set(cache_key, reply, ex=ttl)
                if query_type == "general":
                    redis_client.set(generic_cache_key, reply, ex=ttl)
            return ChatResponse(reply=reply)

    if format_type in {"comparison", "player_batting", "player_bowling"}:
        web_context = extract_stat_focused_context(raw_payload, max_lines=12, query=user_msg)

    context_limit = 12 if format_type == "comparison" else 8
    web_context = "\n".join(web_context.split("\n")[:context_limit])
    fallback_used = False
    if len(web_context.strip()) < 20:
        fallback_used = True
        prompt = build_prompt(user_msg)
        reply = await generate_llm_answer(prompt, temperature=0.1)
        if not is_valid_reply(reply):
            reply = "Couldn't fetch data right now. Try again."
        else:
            reply = enforce_markdown_structure(reply)
    else:
        if format_type == "comparison":
            prompt = build_comparison_prompt(user_msg, web_context)
        elif format_type == "player_bowling":
            prompt = build_bowling_prompt(user_msg, web_context)
        elif format_type == "player_batting":
            prompt = build_batting_prompt(user_msg, web_context)
        elif format_type == "team_stats":
            prompt = build_team_prompt(user_msg, web_context)
        elif format_type == "match_score":
            prompt = build_match_prompt(user_msg, web_context)
        else:
            prompt = build_formatter_prompt(user_msg, web_context)
        reply = await generate_llm_answer(prompt, temperature=0.1)
        if not is_valid_reply(reply):
            reply = "Couldn't fetch data right now. Try again."
        else:
            reply = enforce_markdown_structure(reply)
    if fallback_used:
        note = "Live data may be limited right now." if query_type in {"live_score", "match_result"} else "Latest data may be limited right now."
        reply += f"\n\n(Note: {note})"
    if redis_client is not None:
        ttl = 900 if query_type in {"live_score", "match_result", "standings"} else 1800
        redis_client.set(cache_key, reply, ex=ttl)
        if query_type == "general":
            redis_client.set(generic_cache_key, reply, ex=ttl)
    return ChatResponse(reply=reply)

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)