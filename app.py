import os
import streamlit as st
import requests
import time
from datetime import datetime
from dotenv import load_dotenv

# === 1. LOAD ENV & KEYS ===
load_dotenv()
GEMINI_API_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
BACKEND_URL = "http://localhost:8000"
if not GEMINI_API_KEYS:
    st.error("No Gemini API keys found in .env! Please set GEMINI_API_KEYS=key1,key2,...")
    st.stop()

# === 2. SYSTEM PROMPT ===
def load_system_prompt():
    try:
        with open("system_prompt.txt", encoding="utf-8") as f:
            prompt = f.read()
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        prompt = prompt.replace("{{ $json.current_time }}", now)
        return prompt
    except Exception as e:
        st.error(f"Could not load system prompt: {e}")
        st.stop()

SYSTEM_PROMPT = load_system_prompt()

if "history" not in st.session_state:
    st.session_state.history = []
if "msg_count" not in st.session_state:
    st.session_state.msg_count = 0
if "today" not in st.session_state or st.session_state.today != datetime.now().strftime("%Y-%m-%d"):
    st.session_state.today = datetime.now().strftime("%Y-%m-%d")
    st.session_state.msg_count = 0
if "user_id" not in st.session_state:
    st.session_state.user_id = 25337  # default test user

def gemini_flash_chat(user_message):
    max_retries = 5
    backoff = 1
    for key_idx, api_key in enumerate(GEMINI_API_KEYS):
        for attempt in range(max_retries):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": SYSTEM_PROMPT}]},
                    {"role": "user", "parts": [{"text": user_message}]}
                ]
            }
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return text
                elif response.status_code in [429, 503]:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 16)
                elif response.status_code == 400:
                    return "❌ Ошибка LLM: Похоже, что один из запросов неверно сформирован."
                else:
                    break
            except Exception as e:
                if attempt == max_retries - 1 and key_idx == len(GEMINI_API_KEYS) - 1:
                    return f"❌ Ошибка: {str(e)}"
    return "❌ [All LLM keys overloaded] Please try again later!"

def send_message(user_id, message):
    url = f"{BACKEND_URL}/chat/send"
    payload = {"user_id": user_id, "message": message}
    r = requests.post(url, json=payload, timeout=20)
    try:
        data = r.json()
    except Exception:
        st.error(f"API ERROR: {r.status_code} {r.text}")
        return None
    if "result" in data and data["result"] == "limit":
        st.warning(data.get("message", "Free limit reached. Upgrade to Premium/Pro."))
        return None
    return data.get("reply", "")

st.set_page_config(
    page_title="MIRYAS AI Web Agent",
    layout="centered",
    initial_sidebar_state="collapsed"
)
st.title("🤖 MIRYAS AI Web Agent")
st.markdown("""
**Tariffs:**
- 🆓 Free: 5 free messages per day
- 💎 Premium: 77,000 UZS/month — unlimited text (Payme, Click, PayPal, Stripe, Visa)
- 🔥 Pro: 277,000 UZS/month — unlimited text, voice, TTS/STT, images, advanced answers
""")

user_input = st.text_input("Enter your message:", "")

if st.button("Send") and user_input.strip():
    reply = send_message(st.session_state.user_id, user_input)
    if reply:
        st.session_state.history.append({"role": "user", "msg": user_input})
        st.session_state.history.append({"role": "ai", "msg": reply})

for msg in st.session_state.history:
    role = "🧑" if msg["role"] == "user" else "🤖"
    st.write(f"{role} {msg['msg']}")

st.button("Upgrade to Premium")
st.button("Upgrade to Pro")

st.markdown("5 free messages per day. Unlimited — Premium/Pro | © MIRYAS AI Technologies Inc. 2025 | Stable version. All Rights Reserved | Engineered by MIRYAS AI")



