import re
from config import CRICKET_KEYWORDS

def extract_comparison_entities(query: str) -> tuple[str, str] | None:
    q = " ".join(query.strip().split())

    m = re.search(r"(.+?)\s+(?:vs|versus)\s+(.+)", q, flags=re.IGNORECASE)
    if m:
        left = m.group(1).strip(" ,.-")
        right = m.group(2).strip(" ,.-")
        right = re.split(
            r"\b(in|for|on|during|at|stats|records|record|comparison|compare|who|is|better)\b",
            right,
            flags=re.IGNORECASE,
        )[0].strip(" ,.-")
        if left and right:
            return left, right

    m = re.search(r"compare\s+(.+?)\s+and\s+(.+)", q, flags=re.IGNORECASE)
    if m:
        left = m.group(1).strip(" ,.-")
        right = m.group(2).strip(" ,.-")
        right = re.split(
            r"\b(in|for|on|during|at|stats|records|record|comparison|who|is|better)\b",
            right,
            flags=re.IGNORECASE,
        )[0].strip(" ,.-")
        if left and right:
            return left, right

    return None

def is_cricket_query(query: str) -> bool:
    q = query.lower()
    if any(k in q for k in CRICKET_KEYWORDS):
        return True
    if re.search(r"\bvs\b|\bv\b", q):
        return True
    return False

def normalize_query_for_cache(query: str) -> str:
    q = query.lower()

    # Reduce cache fragmentation for semantically similar phrasing.
    drop_terms = {
        "latest", "current", "now", "today", "recent", "please", "tell", "me", "about"
    }
    cleaned = re.sub(r"[^\w\s]", " ", q)
    tokens = [t for t in cleaned.split() if t and t not in drop_terms]
    return " ".join(tokens)

def is_valid_reply(reply: str | None) -> bool:
    return bool(reply and len(reply.strip()) >= 15)

def enforce_markdown_structure(reply: str) -> str:
    text = (reply or "").strip()
    if not text:
        return (
            "I could not fetch a reliable answer right now.\n\n"
            "- Please retry in a few seconds.\n"
            "- You can also ask a narrower cricket question for a faster response."
        )

    if re.search(r"(^|\n)\s*[-*]\s+", text):
        return text

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        return (
            "I could not fetch a reliable answer right now.\n\n"
            "- Please retry in a few seconds.\n"
            "- You can also ask a narrower cricket question for a faster response."
        )

    top = sentences[0]
    bullets = "\n".join(f"- {s}" for s in sentences[1:5])
    if not bullets:
        bullets = "- " + top
    return f"**Answer**\n- {top}\n\n**Key Points**\n{bullets}"