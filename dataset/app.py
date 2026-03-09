from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import hashlib
import numpy as np
import json
import re
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import uvicorn
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models

class RegisterRequest(BaseModel):
    name: str
    dob: str
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    message: str

class RegisterResponse(BaseModel):
    success: bool
    message: str

class LoginResponse(BaseModel):
    success: bool
    message: str
    user: dict = None

class ChatResponse(BaseModel):
    reply: str
    similarity: Optional[float] = None
    matched_question_similarity: Optional[float] = None

class ErrorResponse(BaseModel):
    error: str

# User Management Logic

users = {}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.post('/register', response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    name = request.name
    dob = request.dob
    username = request.username
    password = request.password

    if not all([name, dob, username, password]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing fields"
        )

    if username in users:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists"
        )

    users[username] = {
        'name': name,
        'dob': dob,
        'password_hash': hash_password(password)
    }

    print("\n[INFO] New user registered:")
    print("Current users:")
    for user, details in users.items():
        print(f"Username: {user}, Name: {details['name']}, DOB: {details['dob']}")
    print("-" * 50)

    return RegisterResponse(success=True, message="User registered successfully")

@app.post('/login', response_model=LoginResponse)
async def login(request: LoginRequest):
    username = request.username
    password = request.password

    print(f"\n[INFO] Login attempt by '{username}'")
    print("Known users:", list(users.keys()))

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing username or password"
        )

    user = users.get(username)
    if not user or user['password_hash'] != hash_password(password):
        print(f"[WARN] Invalid login for user '{username}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    print(f"[SUCCESS] Login successful for user '{username}'")
    return LoginResponse(
        success=True, 
        message="Login successful", 
        user={'name': user['name'], 'username': username}
    )

# Chatbot Logic

with open("embeddings.json", "r") as f:
    data = json.load(f)

chunks = [item["chunk"] for item in data]
embeddings = np.array([item["embedding"] for item in data])
model = SentenceTransformer("all-MiniLM-L6-v2")

greetings = {"hi", "hello", "hey", "hii", "heyy"}

knowledge_base = {
    "what is your name": "I'm CricBOTai, your virtual assistant!",
    "who made you": "I was developed by Ankit, a Computer Science Student and Software Developer",
    "who developed you": "I was developed by Ankit, a Computer Science Student and Software Developer",
    "how can you help me": "I can answer your questions, offer support, and more on cricket!",
    "what can you do": "I can answer your questions, offer support, and more on cricket!",
    "how are you useful": "I can answer your questions, offer support, and more on cricket!"
}

kb_questions = list(knowledge_base.keys())
kb_embeddings = model.encode(kb_questions)

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    user_msg = request.message.strip()
    if not user_msg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No message provided"
        )

    user_msg_lower = user_msg.lower()

    if user_msg_lower in greetings:
        return ChatResponse(
            reply="Hey there! 👋 How can I assist you today?",
            similarity=None,
            matched_question_similarity=None
        )

    user_vec = model.encode([user_msg])

    sims_kb = cosine_similarity(user_vec, kb_embeddings)[0]
    best_kb_index = np.argmax(sims_kb)
    best_kb_sim = sims_kb[best_kb_index]

    if best_kb_sim > 0.3:
        return ChatResponse(
            reply=knowledge_base[kb_questions[best_kb_index]],
            similarity=None,
            matched_question_similarity=float(best_kb_sim)
        )

    sims = cosine_similarity(user_vec, embeddings)[0]
    best_index = np.argmax(sims)
    best_chunk = chunks[best_index]

    pairs = re.split(r'\d+\.\s', best_chunk)
    pairs = [p.strip() for p in pairs if p.strip()]

    best_pair = None
    best_sim = -1

    for pair in pairs:
        if '?' in pair:
            q, a = pair.split('?', 1)
            q = q.strip()
            a = a.strip()
            q_embedding = model.encode([q])
            sim = cosine_similarity(user_vec, q_embedding)[0][0]
            if sim > best_sim:
                best_sim = sim
                best_pair = (q, a)

    if best_pair and best_sim > 0.4:
        reply = best_pair[1]
    elif best_sim < 0.2:
        reply = "Hmm, I don't have an answer for that yet 🤔. You can try rephrasing or ask something else!"
    else:
        reply = best_chunk

    return ChatResponse(
        reply=reply,
        similarity=float(sims[best_index]),
        matched_question_similarity=float(best_sim)
    )

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
