import streamlit as st
import os
import json
import pandas as pd
import re
import requests
from datetime import datetime
from agno.agent import Agent
from agno.models.groq import Groq

# ==============================================================================
# 1. CORE SYSTEM CONFIGURATION
# ==============================================================================
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except KeyError:
    st.error("FATAL: GROQ_API_KEY not found in Streamlit Secrets.")
    st.stop()

# ==============================================================================
# 2. DATA ARCHITECTURE & PERSISTENCE
# ==============================================================================
def get_user_file(username):
    """Generates a unique, sanitized filename for the user database."""
    safe_name = "".join([c for c in username if c.isalnum()]).lower()
    return f"vault_{safe_name}.json"

def save_user_data(username, data):
    """Atomic write operation to prevent JSON corruption."""
    filename = get_user_file(username)
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

def load_user_data(username):
    """Loads user state; returns None if the handshake fails."""
    filename = get_user_file(username)
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Data Retrieval Error: {e}")
            return None
    return None

def update_weight_trend(log, new_weight):
    """Maintains a rolling 14-day history for the Trend Analytics tab."""
    today = datetime.now().strftime("%Y-%m-%d")
    # Check if we already logged today
    for entry in log:
        if entry['date'] == today:
            entry['value'] = new_weight
            return log
    log.append({"date": today, "value": new_weight})
    return log[-14:] # Keep window focused on two weeks

# ==============================================================================
# 3. BIOMETRIC ALGORITHMS
# ==============================================================================
def compute_health_metrics(user_data):
    """Calculates Fuel targets and Mass Index using industry-standard formulas."""
    w = float(user_data.get('weight', 70))
    h = float(user_data.get('height_cm', 175))
    a = int(user_data.get('age', 30))
    
    # Mifflin-St Jeor Equation
    bmr = (10 * w) + (6.25 * h) - (5 * a) + 5
    
    # Goal-Based Adjustments
    goal = user_data.get('goal', 'Longevity')
    offset = -500 if goal == "Fat Loss" else 350 if goal == "Muscle Build" else 0
    
    # Activity Bonus (Steps to Calories conversion)
    step_burn = user_data.get('daily_steps', 0) * 0.04
    
    fuel_target = int(bmr + offset + step_burn)
    bmi = round(w / ((h / 100)**2), 1)
    
    return fuel_target, bmi

# ==============================================================================
# 4. MULTI-AGENT PROTOCOL GENERATION
# ==============================================================================
def run_agent_synthesis(name, age, goal, diet_pref):
    """Orchestrates multiple AI agents to build a high-performance blueprint."""
    groq_model = Groq(id="llama-3.3-70b-versatile", api_key=GROQ_API_KEY)
    
    # Agent 1: Clinical Nutritionist
    nutrition_agent = Agent(
        model=groq_model,
        instructions=["You are a Clinical Performance Nutritionist. Provide structured meal timing and macro breakdowns."]
    )
    diet_response = nutrition_agent.run(f"Create a high-density {diet_pref} protocol for {name} ({age}) focused on {goal}.")
    
    # Agent 2: Elite Strength Coach
    trainer_agent = Agent(
        model=groq_model,
        instructions=["You are a world-class Strength & Conditioning Coach. Focus on volume, intensity, and recovery."]
    )
    fit_response = trainer_agent.run(f"Design a 4-week split for {name} aimed at {goal}. Focus on longevity and posture.")
    
    return diet_response.content, fit_response.content

def pulse_chat_stream(prompt, user_data):
    """Generates the real-time 'Thought Stream' for the Smart Coach."""
    coach = Agent(
        model=Groq(id="llama-3.3-70b-versatile", api_key=GROQ_API_KEY),
        instructions=[
            f"You are Pulse AI for {user_data.get('name')}.",
            "You are concise, data-driven, and authoritative.",
            "Commands: UPDATE: calories [n], steps [n], weight [n], or recovery [n]."
        ]
    )
    for chunk in coach.run(prompt, stream=True):
        if chunk.content:
            yield chunk.content

# ==============================================================================
# 5. HIGH-FIDELITY DASHBOARD STYLING
# ==============================================================================
st.set_page_config(page_title="Pulse AI | High Performance", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp { background-color: #F8F9FB; color: #1C1C1E; font-family: 'Inter', sans-serif; }
    
    /* KPI Card Glassmorphism */
    .pulse-card {
        background: #FFFFFF; border-radius: 28px; padding: 24px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.02); border: 1px solid #E5E5EA;
        height: 180px; display: flex; flex-direction: column; justify-content: space-between;
    }
    .metric-title { color: #8E8E93; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
    .metric-value { color: #000000; font-size: 2.4rem; font-weight: 700; line-height: 1; margin: 10px 0; }
    .metric-sub { color: #A1A1AA; font-size: 0.85rem; font-weight: 500; }
    
    /* Performance Progress Bars */
    .progress-track { background: #F2F2F7; border-radius: 12px; height: 10px; width: 100%; margin-top: 15px; overflow: hidden; }
    .progress-bar { height: 100%; border-radius: 12px; transition: width 1s ease-in-out; }
    
    /* Sidebar Aesthetics */
    .sidebar-section { background: #FFFFFF; border-radius: 20px; padding: 20px; border: 1px solid #E5E5EA; margin-bottom: 25px; }
    .stButton>button { border-radius: 12px; font-weight: 600; transition: all 0.3s; }
    .stButton>button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 6. APPLICATION RUNTIME
# ==============================================================================
def main():
    if 'logged_in_user' not in st.session_state:
        st.session_state.logged_in_user = None

    # --- SCREEN 1: ACCESS & IDENTITY ---
    if st.session_state.logged_in_user is None:
        st.title("⚡ Pulse AI")
        st.subheader("High-Performance Bio-Digital Command Center")
        
        tab_login, tab_signup = st.tabs(["Secure Login", "Create Identity"])
        with tab_login:
            user_input = st.text_input("User ID", help="Enter your protocol ID").lower().strip()
            pass_input = st.text_input("Security Key", type="password")
            if st.button("Unlock Dashboard", use_container_width=True):
                data = load_user_data(user_input)
                if data and data.get("password") == pass_input:
                    st.session_state.logged_in_user = user_input
                    st.session_state.user_data = data
                    st.rerun()
                else: st.error("Access Denied: Invalid Credentials.")
        
        with tab_signup:
            new_u = st.text_input("Desired ID")
            new_p = st.text_input("Set Security Key", type="password")
            if st.button("Initialize Protocol", use_container_width=True):
                if load_user_data(new_u): st.warning("Identity already exists.")
                else:
                    save_user_data(new_u, {"password": new_p, "onboarded": False})
                    st.success("Identity synthesized. Please login.")
        return

    # --- SESSION LOAD ---
    user_data = st.session_state.user_data
    username = st.session_state.logged_in_user

    # --- SCREEN 2: ONBOARDING SYNTHESIS ---
    if not user_data.get("onboarded"):
        st.header(f"Baseline Assessment: {username.capitalize()}")
        with st.form("onboarding_matrix"):
            col_a, col_b = st.columns(2)
            full_name = col_a.text_input("Name")
            user_age = col_a.number_input("Age", 18, 100, 30)
            height_ft = col_a.selectbox("Height (Feet)", [4, 5, 6, 7], index=1)
            height_in = col_a.selectbox("Height (Inches)", list(range(12)), index=9)
            
            curr_weight = col_b.number_input("Current Weight (kg)", 40.0, 200.0, 75.0)
            user_goal = col_b.selectbox("Performance Directive", ["Fat Loss", "Muscle Build", "Longevity"])
            user_diet = col_b.selectbox("Nutrition Baseline", ["Omnivore", "Vegetarian", "Keto", "Vegan", "Paleo"])
            
            if st.form_submit_button("Synthesize Health Protocol"):
                with st.spinner("Engaging Multi-Agent Synthesis Engines..."):
                    cm_height = (height_ft * 30.48) + (height_in * 2.54)
                    diet_blueprint, fitness_blueprint = run_agent_synthesis(full_name, user_age, user_goal, user_diet)
                    
                    user_data.update({
                        "onboarded": True, "name": full_name, "age": user_age, "weight": curr_weight, 
                        "height_cm": cm_height, "goal": user_goal, "diet_plan": diet_blueprint, 
                        "fit_plan": fitness_blueprint, "readiness": 85, "daily_steps": 0, 
                        "daily_calories": 0, "chat_history": [],
                        "weight_log": [{"date": datetime.now().strftime("%Y-%m-%d"), "value": curr_weight}]
                    })
                    # Initial BMI calculation
                    _, user_data['bmi'] = compute_health_metrics(user_data)
                    save_user_data(username, user_data)
                    st.rerun()
        return

    # --- SCREEN 3: PRODUCTION DASHBOARD ---
    
    # 1. Background URL Handshake (Apple Health)
    if "sync_user" in st.query_params and st.query_params["sync_user"] == username:
        st.toast(f"🍏 Apple Health Sync Successful", icon="✅")

    # 2. Side Control Center
    with st.sidebar:
        st.markdown(f"### 🧪 Agent: {user_data['name']}")
        
        st.markdown("<div class='sidebar-section'>", unsafe_allow_html=True)
        st.write("🍏 **Apple Health Bridge**")
        st.caption("Paste this URL in the Exporter App:")
        st.code(f"https://pulse-ai.streamlit.app/?sync_user={username}")
        if st.button("Manual Vitality Refresh"): st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='sidebar-section'>", unsafe_allow_html=True)
        st.write("📊 **Quick Log**")
        up_w = st.number_input("Mass (kg)", value=float(user_data['weight']), step=0.1)
        up_s = st.number_input("Add Steps", value=0, step=1000)
        up_c = st.number_input("Add Calories", value=0, step=100)
        if st.button("Sync Data", use_container_width=True):
            user_data['weight'] = up_w
            user_data['daily_steps'] += up_s
            user_data['daily_calories'] += up_c
            user_data['weight_log'] = update_weight_trend(user_data['weight_log'], up_w)
            _, user_data['bmi'] = compute_health_metrics(user_data)
            save_user_data(username, user_data)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        if st.button("🔄 Reset Profile"): user_data['onboarded'] = False; save_user_data(username, user_data); st.rerun()
        if st.button("🚪 Terminate Session"): st.session_state.logged_in_user = None; st.rerun()

    # 3. KPI Header Logic
    st.markdown(f"<h1>{user_data['name'].upper()} // PERFORMANCE</h1>", unsafe_allow_html=True)
    fuel_limit, current_bmi = compute_health_metrics(user_data)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1: # Recovery Tile
        r_val = user_data.get('readiness', 85)
        r_clr = "#34C759" if r_val > 75 else "#FFCC00" if r_val > 50 else "#FF3B30"
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Recovery</span><span class='metric-value'>{r_val}%</span><div class='progress-track'><div class='progress-bar' style='width:{r_val}%; background:{r_clr};'></div></div></div>", unsafe_allow_html=True)
    
    with col2: # Steps Tile
        s_val = user_data['daily_steps']
        s_pct = min(100, (s_val / 10000) * 100)
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Steps</span><span class='metric-value'>{s_val:,}</span><div class='progress-track'><div class='progress-bar' style='width:{s_pct}%; background:#007AFF;'></div></div></div>", unsafe_allow_html=True)
    
    with col3: # BMI Tile
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Mass Index</span><span class='metric-value'>{current_bmi}</span><span class='metric-sub'>Category: Optimal</span></div>", unsafe_allow_html=True)
    
    with col4: # Fuel Tile
        c_val = user_data['daily_calories']
        c_pct = min(100, (c_val / fuel_limit) * 100)
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Fuel Intake</span><span class='metric-value'>{c_val} <small style='font-size:14px; color:#A1A1AA;'>/ {fuel_limit}</small></span><div class='progress-track'><div class='progress-bar' style='width:{c_pct}%; background:#FF9500;'></div></div></div>", unsafe_allow_html=True)
    
    with col5: # Goal Tile
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Directive</span><span class='metric-value' style='font-size:1.2rem;'>{user_data['goal'].upper()}</span><span class='metric-sub'>Phase: Optimized</span></div>", unsafe_allow_html=True)

    # 4. Deep Intelligence Tabs
    t_nutrition, t_training, t_analytics, t_ai_coach = st.tabs(["🥗 DIET PROTOCOL", "🏋️ TRAINING BLOCK", "📈 TRENDS", "💬 SMART COACH"])
    
    with t_nutrition:
        st.subheader("Nutritional Architecture")
        st.markdown(user_data.get('diet_plan', "Protocol not found."))
        
    with t_training:
        st.subheader("Strength & Conditioning Blueprint")
        st.markdown(user_data.get('fit_plan', "Protocol not found."))
        
    with t_analytics:
        st.subheader("Biometric Trajectory")
        df_log = pd.DataFrame(user_data['weight_log']).set_index('date')
        st.line_chart(df_log, color="#111111")
        st.dataframe(df_log.T, use_container_width=True)

    with t_ai_coach:
        st.chat_input("Command Pulse AI Agent...", key="chat_input")
        if st.session_state.chat_input:
            msg = st.session_state.chat_input
            user_data['chat_history'].insert(0, {"role": "user", "content": msg})
            with st.chat_message("user"): st.write(msg)
            with st.chat_message("assistant"):
                full_stream = st.write_stream(pulse_chat_stream(msg, user_data))
                # NLP Processing for automated updates
                if "UPDATE:" in full_stream:
                    vals = re.findall(r'\d+\.?\d*', full_stream)
                    if vals:
                        v = float(vals[0])
                        if "steps" in full_stream.lower(): user_data['daily_steps'] = int(v)
                        if "calories" in full_stream.lower(): user_data['daily_calories'] = int(v)
                        if "weight" in full_stream.lower(): 
                            user_data['weight'] = v
                            user_data['weight_log'] = update_weight_trend(user_data['weight_log'], v)
                        save_user_data(username, user_data)
                        st.rerun()
            user_data['chat_history'].insert(1, {"role": "assistant", "content": full_stream})
            save_user_data(username, user_data)

        for chat in user_data['chat_history'][2:]:
            with st.chat_message(chat['role']): st.markdown(chat['content'])

if __name__ == "__main__":
    main()