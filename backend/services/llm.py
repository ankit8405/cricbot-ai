

import asyncio
from google import genai
from config import GEMINI_API_KEY
import logging

client = genai.Client(api_key=GEMINI_API_KEY)



async def call_gemini_llm(prompt: str) -> str | None:
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
        return None
    except Exception as e:
        logging.exception("Gemini LLM call failed")
        print("Gemini LLM call failed:", e)
        return None

async def generate_llm_answer(prompt: str) -> str:
    result = await call_gemini_llm(prompt)
    if result and len(result.strip()) > 10:
        return result
    return "Unable to fetch response right now."