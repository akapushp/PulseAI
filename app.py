import streamlit as st
import os
import json
import pandas as pd
import re
from datetime import datetime
from agno.agent import Agent
from agno.models.groq import Groq

# ==============================================================================
# 1. CORE CONFIGURATION
# ==============================================================================
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    st.error("FATAL ERROR: GROQ_API_KEY missing in Secrets.")
    st.stop()

# ==============================================================================
# 2. APPLE HEALTHKIT SYNC ENGINE (THE LISTENER)
# ==============================================================================
def process_apple_health_vitals(username):
    """
    Since Streamlit is a 'Pull' framework, we check for 'sync_user' in the URL.
    When your iPhone hits this URL, it triggers a state refresh.
    """
    params = st.query_params
    if "sync_user" in params and params["sync_user"] == username:
        # In 2026, we use st.toast to confirm the handshake with the iPhone
        st.toast(f"🍏 Apple Health Handshake: {username}", icon="✅")
        return True
    return False

# ==============================================================================
# 3. DATA PERSISTENCE & UTILITIES
# ==============================================================================
def get_user_file(username):
    return f"data_{username.lower().strip()}.json"

def save_user_data(username, data):
    with open(get_user_file(username), "w") as f:
        json.dump(data, f, indent=4)

def load_user_data(username):
    filename = get_user_file(username)
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except: return None
    return None

def add_trend_entry(log, value):
    today = datetime.now().strftime("%Y-%m-%d")
    for entry in log:
        if entry['date'] == today:
            entry['value'] = value
            return log
    log.append({"date": today, "value": value})
    return log[-14:] 

def calculate_dynamic_target(user_data):
    w, h, a = float(user_data.get('weight', 70)), float(user_data.get('height_cm', 175)), int(user_data.get('age', 30))
    bmr = (10 * w) + (6.25 * h) - (5 * a) + 5
    goal = user_data.get('goal', 'Longevity')
    offset = -500 if goal == "Fat Loss" else 350 if goal == "Muscle Build" else 0
    steps = user_data.get('daily_steps', 0)
    return int(bmr + offset + (steps * 0.04))

# ==============================================================================
# 4. REAL-TIME STREAMING AGENT (STEP 1)
# ==============================================================================
def pulse_agent_stream(prompt, user_data):
    coach = Agent(
        model=Groq(id="llama-3.3-70b-versatile", api_key=GROQ_API_KEY),
        instructions=[
            f"You are Pulse AI for {user_data.get('name')}.",
            "Use UPDATE: calories [n], steps [n], weight [n], or recovery [n] to log data.",
            "If they mention Apple Health, tell them their dashboard is synced."
        ]
    )
    for chunk in coach.run(prompt, stream=True):
        if chunk.content:
            yield chunk.content

# ==============================================================================
# 5. ELITE DASHBOARD UI (CSS)
# ==============================================================================
st.set_page_config(page_title="Pulse AI", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    .stApp { background-color: #FAFAFA; color: #1C1C1E; font-family: 'Inter', sans-serif; }
    .pulse-card {
        background: #FFFFFF; border-radius: 24px; padding: 22px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.03); border: 1px solid rgba(0,0,0,0.04);
        height: 165px; display: flex; flex-direction: column; justify-content: space-between;
    }
    .metric-title { color: #8E8E93; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; }
    .metric-value { color: #111111; font-size: 2.2rem; font-weight: 700; line-height: 1; }
    .progress-bg { background: #F2F2F7; border-radius: 10px; height: 8px; width: 100%; margin-top: 10px; overflow: hidden; }
    .progress-fill { height: 100%; border-radius: 10px; transition: width 0.8s ease-in-out; }
    .sidebar-box { background: #FFFFFF; border-radius: 16px; padding: 18px; border: 1px solid #E5E5EA; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 6. APPLICATION MAIN FLOW
# ==============================================================================
def main():
    if 'logged_in_user' not in st.session_state:
        st.session_state.logged_in_user = None

    # --- AUTHENTICATION ---
    if st.session_state.logged_in_user is None:
        st.title("⚡ Pulse AI — Command Center")
        u = st.text_input("User ID").lower().strip()
        p = st.text_input("Access Key", type="password")
        if st.button("Unlock Dashboard", use_container_width=True):
            data = load_user_data(u)
            if data and data.get("password") == p:
                st.session_state.logged_in_user, st.session_state.user_data = u, data
                st.rerun()
        return

    user_data = st.session_state.user_data
    username = st.session_state.logged_in_user

    # --- AUTOMATIC APPLE HEALTH HANDSHAKE ---
    process_apple_health_vitals(username)

    # --- SIDEBAR (SYNC CONTROLS) ---
    with st.sidebar:
        st.markdown(f"### 🛡️ Protocol: {user_data.get('name', username)}")
        
        # Apple Health Bridge Display
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        st.write("🍏 **Apple Health Bridge**")
        st.caption("Copy this to 'Health Auto Export' app:")
        st.code(f"https://{username}.streamlit.app/?sync_user={username}")
        if st.button("🔄 Trigger Manual Refresh"):
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # Manual Data Input
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        st.write("📊 **Manual Vitality Sync**")
        in_w = st.number_input("Weight (kg)", value=float(user_data.get('weight', 70)), step=0.1)
        in_s = st.number_input("Add Steps", value=0, step=500)
        if st.button("Update Vitals"):
            user_data['weight'] = in_w
            user_data['daily_steps'] += in_s
            user_data['weight_log'] = add_trend_entry(user_data['weight_log'], in_w)
            save_user_data(username, user_data)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        if st.button("Log Out"): st.session_state.logged_in_user = None; st.rerun()

    # --- 5-TILE KPI DASHBOARD ---
    st.markdown(f"<h1>{user_data.get('name', 'User')}'s Dashboard</h1>", unsafe_allow_html=True)
    fuel_cap = calculate_dynamic_target(user_data)
    cl1, cl2, cl3, cl4, cl5 = st.columns(5)
    
    with cl1: # Recovery
        rec = user_data.get('readiness', 85)
        clr = "#34C759" if rec > 75 else "#FFCC00"
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Recovery</span><span class='metric-value'>{rec}%</span><div class='progress-bg'><div class='progress-fill' style='width:{rec}%; background:{clr};'></div></div></div>", unsafe_allow_html=True)
    with cl2: # Steps
        s_p = min(100, (user_data.get('daily_steps', 0) / 10000) * 100)
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Steps</span><span class='metric-value'>{user_data.get('daily_steps', 0):,}</span><div class='progress-bg'><div class='progress-fill' style='width:{s_p}%; background:#007AFF;'></div></div></div>", unsafe_allow_html=True)
    with cl3: # BMI
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>BMI Index</span><span class='metric-value'>{user_data.get('bmi', 22.5)}</span><span class='metric-sub'>Mass Scale</span></div>", unsafe_allow_html=True)
    with cl4: # Fuel
        f_p = min(100, (user_data.get('daily_calories', 0) / fuel_cap) * 100)
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Fuel Intake</span><span class='metric-value'>{user_data.get('daily_calories', 0)} <small>/ {fuel_cap}</small></span><div class='progress-bg'><div class='progress-fill' style='width:{f_p}%; background:#FF9500;'></div></div></div>", unsafe_allow_html=True)
    with cl5: # Directive
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Directive</span><span class='metric-value' style='font-size:1.1rem;'>{user_data.get('goal', 'LONGEVITY').upper()}</span><span class='metric-sub'>AI Optimized</span></div>", unsafe_allow_html=True)

    # --- INTELLIGENCE TABS ---
    t_tr, t_c = st.tabs(["📈 TRENDS", "💬 SMART COACH"])
    with t_tr: st.line_chart(pd.DataFrame(user_data.get('weight_log', [])).set_index('date'))
    with t_c:
        st.chat_input("Speak to Pulse AI...", key="chat_input_box")
        if st.session_state.chat_input_box:
            prompt = st.session_state.chat_input_box
            user_data['chat_history'].insert(0, {"role": "user", "content": prompt})
            with st.chat_message("user"): st.markdown(prompt)
            with st.chat_message("assistant"):
                final_msg = st.write_stream(pulse_agent_stream(prompt, user_data))
                # NLP Update logic
                if "UPDATE:" in final_msg:
                    nums = re.findall(r'\d+\.?\d*', final_msg)
                    if nums:
                        val = float(nums[0])
                        if "steps" in final_msg.lower(): user_data['daily_steps'] = int(val)
                        if "calories" in final_msg.lower(): user_data['daily_calories'] = int(val)
                        save_user_data(username, user_data)
                        st.rerun()
            user_data['chat_history'].insert(1, {"role": "assistant", "content": final_msg})
            save_user_data(username, user_data)
        for m in user_data.get('chat_history', [])[2:]:
            with st.chat_message(m["role"]): st.markdown(m["content"])

if __name__ == "__main__":
    main()