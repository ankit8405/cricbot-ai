import os
import re
import streamlit as st
import time
import requests

API_URL = os.getenv("CRICBOT_API_URL", "http://localhost:8000/chat")
AUTO_REFRESH_INTERVAL = 10

def check_backend_health(api_url: str) -> bool:
	try:
		resp = requests.post(api_url, json={"message": "hello"}, timeout=6)
		return resp.status_code == 200
	except Exception:
		return False

def ask_backend(api_url: str, message: str) -> str:
	try:
		resp = requests.post(api_url, json={"message": message}, timeout=45)
		if resp.status_code != 200:
			return f"Backend error: HTTP {resp.status_code}"
		body = resp.json()
		return body.get("reply", "No response from backend.")
	except Exception:
		return "Backend not reachable. Make sure FastAPI server is running."

def parse_scorecard(line: str):
	if " - " not in line or "vs" not in line.lower():
		return None

	try:
		match_name, status_part = line.split(" - ", 1)
		status_part = status_part.strip()
		overs = ""
		if "(" in status_part and ")" in status_part:
			overs = status_part.split("(")[-1].replace(")", "").strip()
			status_part = status_part.split("(")[0].strip()

		return {
			"match": match_name.strip(),
			"score": status_part,
			"overs": overs,
		}
	except Exception:
		return None

def show_scorecards(reply_text: str):
	lines = [line.strip() for line in reply_text.splitlines() if line.strip()]
	cards = []

	for line in lines:
		parsed = parse_scorecard(line)
		if parsed:
			cards.append(parsed)

	# Fallback parser for alternate separators if needed.
	if not cards:
		pattern = re.compile(r"([A-Za-z .]+ vs [A-Za-z .]+)\s*[-:|]\s*([^\n]+)", re.IGNORECASE)
		for m in pattern.finditer(reply_text):
			parsed = parse_scorecard(f"{m.group(1).strip()} - {m.group(2).strip()}")
			if parsed:
				cards.append(parsed)

	if not cards:
		return

	st.markdown("#### Live Match Cards")
	for card in cards[:6]:
		overs_text = f"Overs: {card['overs']}" if card["overs"] else "Overs: N/A"
		st.markdown(
			f"""
			<div class="match-card">
				<div class="match-name">{card['match']}</div>
				<div class="score">{card['score']}</div>
				<div class="overs">{overs_text}</div>
			</div>
			""",
			unsafe_allow_html=True,
		)

def is_live_score_query(query: str) -> bool:
	q = query.lower().strip()
	live_keywords = [
		"live",
		"score",
		"match",
		"today",
		"won",
		"ongoing",
		"current",
		"who is batting",
	]
	static_or_player_keywords = ["stats", "average", "runs", "wickets", "strike rate", "economy", "who is", "explain"]

	if any(k in q for k in static_or_player_keywords) and not any(k in q for k in ["live", "score", "match"]):
		return False

	return any(k in q for k in live_keywords)

st.set_page_config(page_title="CricBOTai", page_icon="", layout="centered")

st.markdown(
	"""
<style>
	.block-container {
		padding-top: 1.2rem;
		max-width: 860px;
	}
	.main-title {
		text-align: center;
		margin-bottom: 0.2rem;
		font-weight: 750;
		letter-spacing: 0.2px;
	}
	.sub-title {
		text-align: center;
		color: #94a3b8;
		margin-top: 0;
		margin-bottom: 1rem;
	}
	[data-testid="stChatMessage"] {
		border-radius: 14px;
		padding: 0.6rem 0.8rem;
		border: 1px solid rgba(148, 163, 184, 0.18);
		background: rgba(15, 23, 42, 0.45);
	}
	.match-card {
		background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.9));
		border: 1px solid rgba(148, 163, 184, 0.22);
		border-radius: 12px;
		padding: 0.75rem 0.85rem;
		margin-bottom: 0.55rem;
	}
	.match-name {
		font-weight: 700;
		margin-bottom: 0.2rem;
	}
	.score {
		font-size: 1.06rem;
		font-weight: 700;
		color: #22c55e;
		margin-bottom: 0.15rem;
	}
	.overs {
		color: #94a3b8;
		font-size: 0.9rem;
	}
</style>
""",
	unsafe_allow_html=True,
)

st.markdown("<h1 class='main-title'>CricBOTai</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Your AI Cricket Assistant</p>", unsafe_allow_html=True)

with st.sidebar:
	st.title("Settings")
	api_url = st.text_input("Backend URL", value=API_URL)
	typing_effect = st.toggle("Typing effect", value=True)
	auto_refresh = st.toggle("Auto Refresh (Live)", value=False)

	if st.button("Clear Chat"):
		st.session_state.messages = []
		st.session_state.last_query = ""
		st.session_state.last_query_is_live = False
		st.rerun()

	st.markdown("---")
	st.caption("Backend Status")
	if check_backend_health(api_url):
		st.success("Connected")
	else:
		st.error("Disconnected")

if "messages" not in st.session_state:
	st.session_state.messages = []

if "last_query" not in st.session_state:
	st.session_state.last_query = ""

if "last_query_is_live" not in st.session_state:
	st.session_state.last_query_is_live = False

for msg in st.session_state.messages:
	with st.chat_message(msg["role"]):
		st.markdown(msg["content"])
		if msg["role"] == "assistant":
			show_scorecards(msg["content"])

user_input = st.chat_input("Ask anything about cricket...")

if user_input:
	st.session_state.last_query = user_input
	st.session_state.last_query_is_live = is_live_score_query(user_input)
	st.session_state.messages.append({"role": "user", "content": user_input})

	with st.chat_message("user"):
		st.markdown(user_input)

	with st.chat_message("assistant"):
		with st.spinner("Thinking..."):
			reply = ask_backend(api_url, user_input)

		if typing_effect and reply:
			placeholder = st.empty()
			full_text = ""
			# Preserve original markdown/newlines while animating.
			tokens = re.findall(r"\S+|\s+", reply)
			for token in tokens:
				full_text += token
				placeholder.markdown(full_text)
				time.sleep(0.02)
		else:
			st.markdown(reply)

		show_scorecards(reply)

	st.session_state.messages.append({"role": "assistant", "content": reply})

if auto_refresh and st.session_state.last_query and st.session_state.last_query_is_live:
	time.sleep(AUTO_REFRESH_INTERVAL)
	latest = ask_backend(api_url, st.session_state.last_query)
	st.session_state.messages.append({"role": "assistant", "content": latest})
	st.rerun()