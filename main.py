import os
from datetime import datetime, date, timedelta
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import asyncpg
import jwt
import httpx

# --- CONFIG ---
load_dotenv()
DATABASE_URL = os.getenv("SUPABASE_DB_URL")
JWT_SECRET = os.getenv("MIRYAS_JWT_SECRET", "super_secret_for_dev_only")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEYS", "").split(",")[0].strip()

# --- FastAPI Instance ---
app = FastAPI(title="MIRYAS AI Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# --- Models ---
class MessageIn(BaseModel):
    user_id: int
    message: str

class UserInterestIn(BaseModel):
    user_id: int
    current_interest: str
    interest_tags: Optional[List[str]] = []

class UserTierOut(BaseModel):
    user_id: int
    tier: str
    daily_message_count: int
    last_interaction_date: Optional[date]
    subscription_expiry_date: Optional[date]
    allow_continue: bool

# --- DB Connection ---
async def get_db():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        await conn.close()

# --- JWT Auth ---
def create_jwt(user_id):
    return jwt.encode(
        {"user_id": user_id, "exp": datetime.utcnow() + timedelta(days=30)},
        JWT_SECRET, algorithm="HS256"
    )

def decode_jwt(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None

async def get_user_id(token: str = Header(..., alias="Authorization")):
    if token.startswith("Bearer "):
        token = token[7:]
    data = decode_jwt(token)
    if not data or "user_id" not in data:
        raise HTTPException(status_code=401, detail="Invalid token")
    return data["user_id"]

# --- Gemini Flash 2.0 LLM Call ---
async def ask_gemini_flash(user_message, system_prompt=None):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": system_prompt or "Ты профессиональный AI ассистент для пользователей из Узбекистана"}]},
            {"role": "user", "parts": [{"text": user_message}]}
        ]
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text

# --- API Endpoints ---

@app.post("/user/init", response_model=UserTierOut)
async def init_user(user_id: int, db=Depends(get_db)):
    query = """
        INSERT INTO public.users (user_id)
        VALUES ($1)
        ON CONFLICT (user_id) DO NOTHING
        RETURNING user_id, tier, daily_message_count, last_interaction_date, subscription_expiry_date, allow_continue
    """
    result = await db.fetchrow(query, user_id)
    if not result:
        result = await db.fetchrow(
            "SELECT user_id, tier, daily_message_count, last_interaction_date, subscription_expiry_date, allow_continue FROM public.users WHERE user_id=$1",
            user_id)
    return dict(result)

@app.get("/user/tier", response_model=UserTierOut)
async def get_user_tier(user_id: int, db=Depends(get_db)):
    result = await db.fetchrow(
        "SELECT user_id, tier, daily_message_count, last_interaction_date, subscription_expiry_date, allow_continue FROM public.users WHERE user_id=$1",
        user_id)
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(result)

@app.post("/chat/send")
async def chat_send(msg: MessageIn, db=Depends(get_db)):
    user = await db.fetchrow("SELECT * FROM public.users WHERE user_id=$1", msg.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    today = date.today()
    if user["tier"] == "free":
        if not user["last_interaction_date"] or user["last_interaction_date"] < today:
            daily_count = 0
        else:
            daily_count = user["daily_message_count"]
        if daily_count >= 5:
            return {"result": "limit", "message": "Free limit reached, upgrade to Premium"}
        await db.execute(
            "UPDATE public.users SET daily_message_count=$1, last_interaction_date=$2 WHERE user_id=$3",
            daily_count + 1, today, msg.user_id
        )
    await db.execute("""
        INSERT INTO public.chat_history (user_id, role, content)
        VALUES ($1, 'user', $2)
    """, msg.user_id, msg.message)
    # --- Реальный вызов LLM
    ai_reply = await ask_gemini_flash(msg.message)
    await db.execute("""
        INSERT INTO public.chat_history (user_id, role, content)
        VALUES ($1, 'ai', $2)
    """, msg.user_id, ai_reply)
    return {"reply": ai_reply, "status": "ok"}

@app.get("/chat/history")
async def get_history(user_id: int, db=Depends(get_db)):
    rows = await db.fetch(
        "SELECT role, content, created_at FROM public.chat_history WHERE user_id=$1 ORDER BY created_at DESC LIMIT 20",
        user_id)
    return [dict(r) for r in rows]

@app.post("/user/interest")
async def set_interest(interest: UserInterestIn, db=Depends(get_db)):
    await db.execute("""
        INSERT INTO public.user_interests (user_id, current_interest, interest_tags, last_updated)
        VALUES ($1, $2, $3, now())
        ON CONFLICT (user_id) DO UPDATE
        SET current_interest=$2, interest_tags=$3, last_updated=now()
    """, interest.user_id, interest.current_interest, interest.interest_tags)
    return {"status": "saved"}

@app.get("/user/interest")
async def get_interest(user_id: int, db=Depends(get_db)):
    r = await db.fetchrow("SELECT current_interest, interest_tags FROM public.user_interests WHERE user_id=$1", user_id)
    return dict(r) if r else {}

@app.get("/")
async def root():
    return {"status": "MIRYAS AI backend OK"}









