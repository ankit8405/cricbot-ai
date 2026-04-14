from config import LLM_MODEL, GROQ_API_KEY, http_client

async def call_groq_llm(prompt: str, model: str, temperature: float = 0.2) -> str | None:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a cricket-only assistant. If query is not cricket-related, refuse politely."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }
    try:
        resp = await http_client.post(url, headers=headers, json=payload)
        if resp.status_code == 200:
            result = resp.json()
            if isinstance(result, dict):
                choices = result.get("choices", [])
                if isinstance(choices, list) and choices:
                    first = choices[0] if isinstance(choices[0], dict) else {}
                    message = first.get("message", {}) if isinstance(first, dict) else {}
                    content = message.get("content") if isinstance(message, dict) else None
                    if isinstance(content, str) and content.strip():
                        return content
        return None
    except Exception:
        return None

async def generate_llm_answer(prompt: str, temperature: float = 0.2) -> str:
    result = await call_groq_llm(prompt, LLM_MODEL, temperature=temperature)
    if result and len(result.strip()) > 10:
        return result
    return "Unable to fetch response right now."