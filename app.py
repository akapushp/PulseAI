import streamlit as st
import os
import json
import pandas as pd
import re
from datetime import datetime
from agno.agent import Agent
from agno.models.groq import Groq

# --- 1. SECURE CONFIGURATION ---
# This ensures the app doesn't crash if the key is missing
try:
    my_groq_key = st.secrets["GROQ_API_KEY"]
except Exception:
    st.error("FATAL ERROR: GROQ_API_KEY not found in Streamlit Secrets.")
    st.stop()

# --- 2. DATA PERSISTENCE ENGINE ---
def get_user_file(username):
    """Generates a unique filename for each user."""
    return f"data_{username}.json"

def save_user_data(username, data):
    """Saves the entire user state to a JSON file."""
    with open(get_user_file(username), "w") as f:
        json.dump(data, f, indent=4)

def load_user_data(username):
    """Loads user data; returns None if the user doesn't exist."""
    filename = get_user_file(username)
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def add_trend_entry(log, value):
    """Updates the 14-day rolling weight trend."""
    today = datetime.now().strftime("%Y-%m-%d")
    # Check if we already logged weight today; if so, update it
    for entry in log:
        if entry['date'] == today:
            entry['value'] = value
            return log
    # Otherwise, add a new entry
    log.append({"date": today, "value": value})
    # Maintain only the last 14 entries for clean charting
    return log[-14:] 

# --- 3. CORE HEALTH ALGORITHMS ---
def calculate_dynamic_target(user_data):
    """
    Implements the Mifflin-St Jeor Equation with dynamic activity bonuses.
    Calculates exactly how much 'Fuel' the user needs based on movement.
    """
    w = float(user_data.get('weight', 70))
    h = float(user_data.get('height_cm', 170))
    a = int(user_data.get('age', 30))
    
    # Base Metabolic Rate (BMR)
    bmr = (10 * w) + (6.25 * h) - (5 * a) + 5
    
    # Goal-based adjustments
    goal = user_data.get('goal', 'Longevity')
    if goal == "Fat Loss":
        goal_offset = -500
    elif goal == "Muscle Build":
        goal_offset = 350
    else:
        goal_offset = 0
        
    # Activity Bonus: 0.04 calories burned per step recorded
    steps = user_data.get('daily_steps', 0)
    step_bonus = steps * 0.04
    
    return int(bmr + goal_offset + step_bonus)

# --- 4. AI AGENT & NATURAL LANGUAGE PROCESSING ---
def handle_chat():
    """Processes user messages and extracts health metrics automatically."""
    prompt = st.session_state.chat_input_box
    if not prompt: 
        return
    
    user_data = st.session_state.user_data
    username = st.session_state.logged_in_user
    
    # Store user message in history
    user_data['chat_history'].insert(0, {"role": "user", "content": prompt})
    
    # Initialize the Smart Coach
    coach = Agent(
        model=Groq(id="llama-3.3-70b-versatile", api_key=my_groq_key), 
        instructions=[
            f"You are Pulse AI, the elite health coach for {user_data.get('name')}.",
            "You can update user metrics using specific commands.",
            "If the user reports food/calories, reply with: UPDATE: calories [value].",
            "If the user reports steps, reply with: UPDATE: steps [value].",
            "If the user reports weight, reply with: UPDATE: weight [value].",
            "If the user feels tired/recovered, reply with: UPDATE: recovery [value].",
            "Always be encouraging, data-driven, and concise."
        ]
    )
    
    # Get AI response
    response_obj = coach.run(prompt)
    ai_message = response_obj.content
    
    # Command Parsing Logic
    if "UPDATE:" in ai_message:
        extracted_values = re.findall(r'\d+\.?\d*', ai_message)
        if extracted_values:
            val = float(extracted_values[0])
            if "calories" in ai_message.lower():
                user_data['daily_calories'] += int(val)
            elif "steps" in ai_message.lower():
                user_data['daily_steps'] += int(val)
            elif "recovery" in ai_message.lower():
                user_data['readiness'] = min(100, max(0, int(val)))
            elif "weight" in ai_message.lower():
                user_data['weight'] = val
                user_data['bmi'] = round(val / ((user_data['height_cm'] / 100)**2), 1)
                user_data['weight_log'] = add_trend_entry(user_data['weight_log'], val)
    else:
        # Standard conversation
        user_data['chat_history'].insert(1, {"role": "assistant", "content": ai_message})
    
    # Persistence
    save_user_data(username, user_data)
    st.session_state.chat_input_box = ""

# --- 5. GLOBAL UI & CSS DESIGN ---
st.set_page_config(page_title="Pulse AI", page_icon="⚡", layout="wide")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp { background-color: #FAFAFA; color: #1C1C1E; font-family: 'Inter', sans-serif; }
    
    /* KPI Card Styling */
    .pulse-card {
        background: #FFFFFF; border-radius: 24px; padding: 22px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.03); border: 1px solid rgba(0,0,0,0.04);
        height: 165px; display: flex; flex-direction: column; justify-content: space-between;
    }
    .metric-title { color: #8E8E93; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; }
    .metric-value { color: #111111; font-size: 2.2rem; font-weight: 700; line-height: 1; }
    .metric-sub { color: #8E8E93; font-size: 0.85rem; margin-top: 4px; }
    
    /* Progress Bars */
    .progress-bg { background: #F2F2F7; border-radius: 10px; height: 8px; width: 100%; margin-top: 10px; overflow: hidden; }
    .progress-fill { height: 100%; border-radius: 10px; transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1); }
    
    /* Sidebar & Navigation */
    .sidebar-box { background: #FFFFFF; border-radius: 16px; padding: 18px; border: 1px solid #E5E5EA; margin-bottom: 20px; }
    .stTabs [aria-selected="true"] { background: #111111 !important; color: #FFFFFF !important; border-radius: 12px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 6. MAIN APPLICATION LOGIC ---
def main():
    if 'logged_in_user' not in st.session_state:
        st.session_state.logged_in_user = None

    # --- A. LOGIN / REGISTER SYSTEM ---
    if st.session_state.logged_in_user is None:
        st.title("⚡ Pulse AI — Digital Health")
        tab_log, tab_reg = st.tabs(["Secure Login", "Create Account"])
        
        with tab_log:
            u_in = st.text_input("Username").lower().strip()
            p_in = st.text_input("Password", type="password")
            if st.button("Access Dashboard", use_container_width=True):
                data = load_user_data(u_in)
                if data and data.get("password") == p_in:
                    st.session_state.logged_in_user = u_in
                    st.session_state.user_data = data
                    st.rerun()
                else:
                    st.error("Authentication failed. Please check your credentials.")
        
        with tab_reg:
            u_new = st.text_input("New Username").lower().strip()
            p_new = st.text_input("New Password", type="password")
            if st.button("Register Account", use_container_width=True):
                if u_new and p_new:
                    if os.path.exists(get_user_file(u_new)):
                        st.error("Username already exists.")
                    else:
                        save_user_data(u_new, {"password": p_new, "onboarded": False})
                        st.success("Account created successfully! Please login.")
        return

    # --- B. ONBOARDING & AI PROTOCOL GENERATION ---
    user_data = st.session_state.user_data
    username = st.session_state.logged_in_user

    if not user_data.get("onboarded"):
        st.title(f"Personalize Your Protocol, {username.capitalize()}")
        with st.form("onboarding_suite"):
            col_a, col_b = st.columns(2)
            name = col_a.text_input("Full Name")
            age = col_a.number_input("Age", 18, 100, 28)
            f_ht = col_a.selectbox("Height (Feet)", [4, 5, 6, 7], index=1)
            i_ht = col_a.selectbox("Height (Inches)", list(range(12)), index=9)
            
            weight = col_b.number_input("Weight (kg)", 40.0, 200.0, 70.0)
            goal = col_b.selectbox("Main Objective", ["Fat Loss", "Muscle Build", "Longevity", "Performance"])
            diet = col_b.selectbox("Dietary Style", ["Vegetarian", "Non-vegetarian", "Keto", "Vegan", "Paleo"])
            
            if st.form_submit_button("Generate Bio-Digital Plan"):
                with st.spinner("Agent Pulse is crafting your diet and training protocols..."):
                    h_total = (f_ht * 30.48) + (i_ht * 2.54)
                    model_engine = Groq(id="llama-3.3-70b-versatile", api_key=my_groq_key)
                    
                    # AI Core generation
                    diet_res = Agent(model=model_engine).run(f"Plan a {diet} diet for {goal}").content
                    work_res = Agent(model=model_engine).run(f"Plan a workout for {goal}").content
                    
                    user_data.update({
                        "onboarded": True,
                        "name": name, "age": age, "weight": weight, "height_cm": h_total,
                        "goal": goal, "diet_plan": diet_res, "fit_plan": work_res,
                        "readiness": 85, "daily_steps": 0, "daily_calories": 0,
                        "bmi": round(weight / ((h_total/100)**2), 1),
                        "chat_history": [],
                        "weight_log": [{"date": datetime.now().strftime("%Y-%m-%d"), "value": weight}]
                    })
                    save_user_data(username, user_data)
                    st.rerun()
        return

    # --- C. SIDEBAR CONTROL CENTER ---
    with st.sidebar:
        st.markdown(f"### 🛡️ Pulse Command: {user_data.get('name')}")
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        st.write("📋 **Update Vitals**")
        
        # Inputs
        upd_weight = st.number_input("Body Weight (kg)", value=float(user_data['weight']), step=0.1)
        upd_recover = st.slider("Readiness/Recovery %", 0, 100, int(user_data.get('readiness', 85)))
        upd_steps = st.number_input("Add Steps", value=0, step=500)
        upd_cals = st.number_input("Add Calories", value=0, step=100)
        
        if st.button("Sync Data to Cloud", use_container_width=True):
            user_data['weight'] = upd_weight
            user_data['readiness'] = upd_recover
            user_data['daily_steps'] += upd_steps
            user_data['daily_calories'] += upd_cals
            user_data['bmi'] = round(upd_weight / ((user_data['height_cm'] / 100)**2), 1)
            user_data['weight_log'] = add_trend_entry(user_data['weight_log'], upd_weight)
            save_user_data(username, user_data)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        if st.button("Log Out", use_container_width=True):
            st.session_state.logged_in_user = None
            st.rerun()
            
        if st.button("Factory Reset Profile", use_container_width=True):
            user_data["onboarded"] = False
            save_user_data(username, user_data)
            st.rerun()

    # --- D. THE 5-TILE KPI COMMAND CENTER ---
    st.markdown(f"<h1>{user_data['name']}'s Health Dashboard</h1>", unsafe_allow_html=True)
    
    current_fuel_target = calculate_dynamic_target(user_data)
    t_1, t_2, t_3, t_4, t_5 = st.columns(5)
    
    with t_1: # Recovery
        rec = user_data.get('readiness', 85)
        rec_color = "#34C759" if rec > 75 else "#FFCC00" if rec > 40 else "#FF3B30"
        st.markdown(f"""
            <div class='pulse-card'>
                <span class='metric-title'>Recovery</span>
                <span class='metric-value'>{rec}%</span>
                <div class='progress-bg'><div class='progress-fill' style='width:{rec}%; background:{rec_color};'></div></div>
            </div>
        """, unsafe_allow_html=True)

    with t_2: # Steps
        step_val = user_data.get('daily_steps', 0)
        step_pct = min(100, (step_val / 10000) * 100)
        st.markdown(f"""
            <div class='pulse-card'>
                <span class='metric-title'>Steps</span>
                <span class='metric-value'>{step_val:,}</span>
                <div class='progress-bg'><div class='progress-fill' style='width:{step_pct}%; background:#007AFF;'></div></div>
            </div>
        """, unsafe_allow_html=True)

    with t_3: # BMI
        bmi_val = user_data.get('bmi', 22.0)
        st.markdown(f"""
            <div class='pulse-card'>
                <span class='metric-title'>BMI Index</span>
                <span class='metric-value'>{bmi_val}</span>
                <span class='metric-sub'>Proportional Status</span>
            </div>
        """, unsafe_allow_html=True)

    with t_4: # Fuel (The Dynamic Tile)
        cal_val = user_data.get('daily_calories', 0)
        fuel_pct = min(100, (cal_val / current_fuel_target) * 100)
        st.markdown(f"""
            <div class='pulse-card'>
                <span class='metric-title'>Fuel Status</span>
                <span class='metric-value'>{cal_val} <small style='font-size:14px; color:#8E8E93;'>/ {current_fuel_target}</small></span>
                <div class='progress-bg'><div class='progress-fill' style='width:{fuel_pct}%; background:#FF9500;'></div></div>
            </div>
        """, unsafe_allow_html=True)

    with t_5: # Goal Focus
        focus_goal = user_data.get('goal', 'LONGEVITY').upper()
        st.markdown(f"""
            <div class='pulse-card'>
                <span class='metric-title'>Active Focus</span>
                <span class='metric-value' style='font-size:1.1rem;'>{focus_goal}</span>
                <span class='metric-sub'>Dynamic Protocol</span>
            </div>
        """, unsafe_allow_html=True)

    # --- E. CONTENT TABS (Nutrition, Training, Trends, AI) ---
    tab_nut, tab_train, tab_trend, tab_coach = st.tabs(["🥗 NUTRITION", "🏋️ TRAINING", "📈 TRENDS", "💬 SMART COACH"])
    
    with tab_nut: 
        st.markdown("### AI Nutrition Protocol")
        st.markdown(f"<div style='background:white; padding:30px; border-radius:24px; border:1px solid #EEE; color:#1C1C1E; line-height:1.6;'>{user_data['diet_plan']}</div>", unsafe_allow_html=True)
    
    with tab_train: 
        st.markdown("### Precision Strength & Cardio Plan")
        st.markdown(f"<div style='background:white; padding:30px; border-radius:24px; border:1px solid #EEE; color:#1C1C1E; line-height:1.6;'>{user_data['fit_plan']}</div>", unsafe_allow_html=True)
    
    with tab_trend:
        st.markdown("### Weight Evolution (14-Day View)")
        trend_df = pd.DataFrame(user_data['weight_log']).set_index('date')
        st.line_chart(trend_df, color="#007AFF")
            
    with tab_coach:
        st.markdown("### Talk to Pulse AI")
        st.text_input("Enter message...", key="chat_input_box", on_change=handle_chat, placeholder="Ask a question or log data (e.g., 'Log 500 steps')")
        st.markdown("---")
        for chat_entry in user_data['chat_history']:
            with st.chat_message(chat_entry["role"]):
                st.markdown(chat_entry["content"])

if __name__ == "__main__":
    main()