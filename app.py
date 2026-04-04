import streamlit as st
import os
import json
import pandas as pd
import re
from datetime import datetime
from agno.agent import Agent
from agno.models.groq import Groq

# --- 1. PROD CONFIG ---
try:
    my_groq_key = st.secrets["GROQ_API_KEY"]
except:
    st.error("Missing GROQ_API_KEY in Streamlit Secrets.")
    st.stop()

# --- 2. DATA PERSISTENCE ---
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
                data = json.load(f)
                # Ensure all keys exist for older files
                defaults = {'weight_log': [], 'recovery_log': [], 'chat_history': [], 'daily_calories': 0, 'daily_steps': 0, 'readiness': 100}
                for k, v in defaults.items():
                    if k not in data: data[k] = v
                return data
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

# --- 3. CHAT CALLBACK ---
def handle_chat():
    prompt = st.session_state.chat_input_box
    if not prompt: return
    
    user_data = st.session_state.user_data
    username = st.session_state.logged_in_user
    
    user_data['chat_history'].insert(0, {"role": "user", "content": prompt})
    
    coach = Agent(
        model=Groq(id="llama-3.3-70b-versatile", api_key=my_groq_key), 
        instructions=[f"Pulse Engine for {user_data['name']}. Log metrics as 'UPDATE: [type] [value]' or give short coaching tips."]
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

# --- 4. UI STYLING (iOS Premium) ---
st.set_page_config(page_title="Pulse AI", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp { background-color: #FAFAFA; color: #1C1C1E; font-family: 'Inter', sans-serif; }
    .pulse-card {
        background: #FFFFFF; border-radius: 24px; padding: 22px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.03); border: 1px solid rgba(0,0,0,0.04);
        height: 160px; display: flex; flex-direction: column; justify-content: space-between;
    }
    .metric-title { color: #8E8E93; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; }
    .metric-value { color: #111111; font-size: 2rem; font-weight: 700; line-height: 1; }
    .progress-bg { background: #F2F2F7; border-radius: 10px; height: 8px; width: 100%; margin-top: 10px; overflow: hidden; }
    .progress-fill { height: 100%; border-radius: 10px; transition: width 0.6s ease; }
    .stTabs [aria-selected="true"] { background: #111111 !important; color: #FFFFFF !important; border-radius: 12px !important; }
    </style>
    """, unsafe_allow_html=True)

def main():
    if 'logged_in_user' not in st.session_state:
        st.session_state.logged_in_user = None

    # --- LOGIN ---
    if st.session_state.logged_in_user is None:
        st.title("⚡ Pulse AI")
        u = st.text_input("Username").lower().strip()
        p = st.text_input("Password", type="password")
        if st.button("Access Dashboard", use_container_width=True):
            if u and p == "pulse2026":
                st.session_state.logged_in_user = u
                st.session_state.user_data = load_user_data(u)
                st.rerun()
        return

    # --- ONBOARDING ---
    user_data = st.session_state.user_data
    username = st.session_state.logged_in_user

    if user_data is None:
        st.title("Setup Your Protocol")
        with st.form("onboard"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Name")
            age = c1.number_input("Age", 18, 100, 25)
            weight = c2.number_input("Weight (kg)", 40.0, 200.0, 75.0)
            goal = c2.selectbox("Goal", ["Fat Loss", "Muscle Build", "Longevity", "Strength"])
            height = st.slider("Height (cm)", 120, 220, 175)
            diet = st.selectbox("Diet", ["Vegetarian", "Non-vegetarian", "Keto", "Vegan"])
            
            if st.form_submit_button("Generate AI Plans"):
                with st.spinner("AI is crafting your plan..."):
                    model = Groq(id="llama-3.3-70b-versatile", api_key=my_groq_key)
                    diet_p = Agent(model=model).run(f"Meal plan for {diet} goal {goal}").content
                    fit_p = Agent(model=model).run(f"Workout for {goal}").content
                    new_data = {
                        "name": name, "weight": weight, "height_cm": height, "goal": goal,
                        "diet_plan": diet_p, "fit_plan": fit_p, "readiness": 100, 
                        "daily_steps": 0, "daily_calories": 0, "calorie_target": 2500,
                        "bmi": round(weight / ((height/100)**2), 1),
                        "chat_history": [], "weight_log": [], "recovery_log": []
                    }
                    save_user_data(username, new_data)
                    st.session_state.user_data = new_data
                    st.rerun()
        return

    # --- DASHBOARD ---
    st.sidebar.title(f"👤 {user_data['name']}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in_user = None
        st.rerun()

    st.markdown("<h1>⚡ Pulse Dashboard</h1>", unsafe_allow_html=True)
    
    # 5-Column KPI Row
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: # Recovery
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Recovery</span><span class='metric-value'>{user_data['readiness']}%</span><div class='progress-bg'><div class='progress-fill' style='width:{user_data['readiness']}%; background:#34C759;'></div></div></div>", unsafe_allow_html=True)
    with k2: # Steps
        s_pct = min(100, (user_data['daily_steps'] / 10000) * 100)
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Steps</span><span class='metric-value'>{user_data['daily_steps']:,}</span><div class='progress-bg'><div class='progress-fill' style='width:{s_pct}%; background:#007AFF;'></div></div></div>", unsafe_allow_html=True)
    with k3: # BMI Dial
        bmi = user_data['bmi']
        dash = 125.66 * (1 - min(bmi, 40) / 40)
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>BMI Index</span><div style='display:flex; justify-content:space-between; align-items:center;'><span class='metric-value'>{bmi}</span><svg viewBox='0 0 100 60' width='50px'><path d='M 10 50 A 40 40 0 0 1 90 50' fill='none' stroke='#EEE' stroke-width='12' stroke-linecap='round' /><path d='M 10 50 A 40 40 0 0 1 90 50' fill='none' stroke='#007AFF' stroke-width='12' stroke-linecap='round' stroke-dasharray='125.66' stroke-dashoffset='{dash}'/></svg></div></div>", unsafe_allow_html=True)
    with k4: # Calories
        c_pct = min(100, (user_data['daily_calories'] / user_data['calorie_target']) * 100)
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Fuel (kcal)</span><span class='metric-value'>{user_data['daily_calories']}</span><div class='progress-bg'><div class='progress-fill' style='width:{c_pct}%; background:#FF9500;'></div></div></div>", unsafe_allow_html=True)
    with k5: # Goal
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Goal Focus</span><span class='metric-value' style='font-size:1.2rem;'>{user_data['goal']}</span></div>", unsafe_allow_html=True)

    # Tabs
    t1, t2, t3, t4 = st.tabs(["🥗 NUTRITION", "🏋️ TRAINING", "📈 TRENDS", "💬 SMART COACH"])
    
    with t1: st.markdown(f"<div style='background:white; padding:20px; border-radius:20px; border:1px solid #EEE;'>{user_data['diet_plan']}</div>", unsafe_allow_html=True)
    with t2: st.markdown(f"<div style='background:white; padding:20px; border-radius:20px; border:1px solid #EEE;'>{user_data['fit_plan']}</div>", unsafe_allow_html=True)
    with t3:
        ca, cb = st.columns(2)
        if user_data['weight_log']:
            with ca: st.markdown("**Weight Trend**"); st.line_chart(pd.DataFrame(user_data['weight_log']).set_index('date'))
        if user_data['recovery_log']:
            with cb: st.markdown("**Recovery Trend**"); st.line_chart(pd.DataFrame(user_data['recovery_log']).set_index('date'))
    with t4:
        st.text_input("Command Coach", key="chat_input_box", on_change=handle_chat, placeholder="Log 500 calories...")
        st.markdown("---")
        for msg in user_data['chat_history']:
            with st.chat_message(msg["role"]): st.write(msg["content"])

if __name__ == "__main__":
    main()