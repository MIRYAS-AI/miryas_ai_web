import streamlit as st

st.set_page_config(
    page_title="MIRYAS AI Web Agent",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.title("🤖 MIRYAS AI Web Agent")
st.markdown("""
Welcome to **MIRYAS AI Web Agent**!  
- Multilingual LLM chatbot for Uzbek, Russian, Tajik, English  
- 5 messages daily for free  
- Premium/Pro: unlimited, TTS, STT, image generation (coming soon!)  
- Try sending a message below:
""")

# Dummy chat interface (for MVP)
if "history" not in st.session_state:
    st.session_state.history = []

user_input = st.text_input("Your message (Uzbek, Russian, Tajik, English):", "")

if st.button("Send") and user_input.strip():
    # Emulate LLM reply (stub)
    bot_reply = f"🤖 [Beta] You said: {user_input}\n(Real AI agent logic coming soon!)"
    st.session_state.history.append({"role": "user", "msg": user_input})
    st.session_state.history.append({"role": "ai", "msg": bot_reply})

for msg in st.session_state.history:
    role = "🧑" if msg["role"] == "user" else "🤖"
    st.write(f"{role} {msg['msg']}")
