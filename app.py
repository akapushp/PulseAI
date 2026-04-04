import streamlit as st
import os
import json
import pandas as pd
import re
from datetime import datetime
from agno.agent import Agent
from agno.models.groq import Groq

# --- 1. PROD CONFIG: SECRETS & KEYS ---
try:
    my_groq_key = st.secrets["GROQ_API_KEY"]
except Exception:
    st.error("Error: GROQ_API_KEY not found in Streamlit Secrets.")
    st.stop()

# --- 2. DATA PERSISTENCE (Multi-User) ---
def get_user_file(username):
    return f"data_{username}.json"

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

# --- 3. CHAT LOGIC (Loop-Free) ---
def handle_chat():
    prompt = st.session_state.chat_input_box
    if not prompt: return
    
    user_data = st.session_state.user_data
    username = st.session_state.logged_in_user
    
    user_data['chat_history'].insert(0, {"role": "user", "content": prompt})
    
    coach = Agent(
        model=Groq(id="llama-3.3-70b-versatile", api_key=my_groq_key), 
        instructions=[f"You are Pulse AI for {user_data['name']}. Goal: {user_data['goal']}. Log metrics as 'UPDATE: [type] [value]' or give 1-2 sentence coaching tips."]
    )
    
    response = coach.run(prompt).content
    
    if "UPDATE:" in response:
        if "calories" in response.lower():
            val = re.findall(r'\d+', response)
            if val: user_data['daily_calories'] += int(val[0])
        elif "steps" in response.lower():
            val = re.findall(r'\d+', response)
            if val: user_data['daily_steps'] += int(val[0])
        elif "weight" in response.lower():
            val = re.findall(r'\d+\.?\d*', response)
            if val: 
                w = float(val[0])
                user_data['weight'] = w
                user_data['bmi'] = round(w / ((user_data['height_cm'] / 100)**2), 1)
                user_data['weight_log'] = add_trend_entry(user_data['weight_log'], w)
    else:
        user_data['chat_history'].insert(1, {"role": "assistant", "content": response})
    
    save_user_data(username, user_data)
    st.session_state.chat_input_box = ""

# --- 4. UI STYLING ---
st.set_page_config(page_title="Pulse AI", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    .stApp { background-color: #FAFAFA; color: #1C1C1E; font-family: 'Inter', sans-serif; }
    .pulse-card {
        background: #FFFFFF; border-radius: 20px; padding: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.02); border: 1px solid #EEE;
        height: 150px; display: flex; flex-direction: column; justify-content: center;
    }
    .metric-title { color: #8E8E93; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; }
    .metric-value { color: #111; font-size: 2rem; font-weight: 700; }
    .progress-bg { background: #F2F2F7; border-radius: 10px; height: 6px; width: 100%; margin-top: 10px; overflow: hidden; }
    .progress-fill { height: 100%; border-radius: 10px; transition: width 0.6s ease; }
    </style>
    """, unsafe_allow_html=True)

# --- 5. MAIN APP ROUTING ---
def main():
    if 'logged_in_user' not in st.session_state:
        st.session_state.logged_in_user = None

    # --- A. LOGIN PAGE ---
    if st.session_state.logged_in_user is None:
        st.title("⚡ Pulse AI Login")
        u = st.text_input("Username").lower().strip()
        p = st.text_input("Password", type="password")
        if st.button("Enter Portal", use_container_width=True):
            if u and p == "pulse2026":
                st.session_state.logged_in_user = u
                st.session_state.user_data = load_user_data(u)
                st.rerun()
            else:
                st.error("Invalid Login")
        return

    # --- B. ONBOARDING PAGE ---
    username = st.session_state.logged_in_user
    if st.session_state.user_data is None:
        st.title(f"Welcome, {username.capitalize()}")
        st.subheader("Initialize your Health Protocol")
        with st.form("onboarding_form"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Full Name")
            age = c1.number_input("Age", 18, 100, 30)
            weight = c2.number_input("Weight (kg)", 40.0, 200.0, 75.0)
            goal = c2.selectbox("Goal", ["Fat Loss", "Muscle Build", "Longevity"])
            height = st.slider("Height (cm)", 120, 220, 175)
            
            if st.form_submit_button("Launch Dashboard"):
                new_data = {
                    "name": name, "weight": weight, "height_cm": height, "goal": goal,
                    "readiness": 100, "daily_steps": 0, "daily_calories": 0, "calorie_target": 2500,
                    "bmi": round(weight / ((height/100)**2), 1),
                    "chat_history": [], "weight_log": [], "recovery_log": [], "diet_plan": "Genereating...", "fit_plan": "Generating..."
                }
                save_user_data(username, new_data)
                st.session_state.user_data = new_data
                st.rerun()
        return

    # --- C. DASHBOARD PAGE ---
    data = st.session_state.user_data
    
    # Sidebar
    st.sidebar.title(f"Hi, {data['name']}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in_user = None
        st.rerun()

    st.title("⚡ Pulse Dashboard")
    
    # KPI Row
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Recovery</span><span class='metric-value'>{data['readiness']}%</span><div class='progress-bg'><div class='progress-fill' style='width:{data['readiness']}%; background:#34C759;'></div></div></div>", unsafe_allow_html=True)
    with k2:
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Steps</span><span class='metric-value'>{data['daily_steps']}</span><div class='progress-bg'><div class='progress-fill' style='width:{(data['daily_steps']/10000)*100}%; background:#007AFF;'></div></div></div>", unsafe_allow_html=True)
    with k3:
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>BMI Index</span><span class='metric-value'>{data['bmi']}</span></div>", unsafe_allow_html=True)
    with k4:
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Fuel</span><span class='metric-value'>{data['daily_calories']} kcal</span></div>", unsafe_allow_html=True)

    # Tabs
    t1, t2 = st.tabs(["💬 SMART COACH", "📈 HISTORY"])
    
    with t1:
        st.text_input("Command Coach (e.g. 'Log 500 cals')", key="chat_input_box", on_change=handle_chat)
        st.markdown("---")
        for msg in data['chat_history']:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                
    with t2:
        if data['weight_log']:
            st.line_chart(pd.DataFrame(data['weight_log']).set_index('date'))
        else:
            st.info("No log data yet.")

if __name__ == "__main__":
    main()