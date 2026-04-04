import streamlit as st
import os
import json
import pandas as pd
import re
from datetime import datetime
from agno.agent import Agent
from agno.models.groq import Groq

# --- 1. SECURE CONFIGURATION ---
# Robust error handling for API keys in production environments
try:
    my_groq_key = st.secrets["GROQ_API_KEY"]
except Exception:
    st.error("FATAL ERROR: GROQ_API_KEY not found in Streamlit Secrets.")
    st.stop()

# --- 2. DATA PERSISTENCE ENGINE ---
def get_user_file(username):
    """Generates a unique filename for each user's database."""
    return f"data_{username}.json"

def save_user_data(username, data):
    """Saves the entire user state to a local JSON file."""
    with open(get_user_file(username), "w") as f:
        json.dump(data, f, indent=4)

def load_user_data(username):
    """Loads user data; returns None if the user is not found."""
    filename = get_user_file(username)
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def add_trend_entry(log, value):
    """Updates the 14-day rolling weight trend log."""
    today = datetime.now().strftime("%Y-%m-%d")
    # Update entry if today's date already exists
    for entry in log:
        if entry['date'] == today:
            entry['value'] = value
            return log
    # Otherwise, append new weight entry
    log.append({"date": today, "value": value})
    # Maintain a clean 14-day window for charting
    return log[-14:] 

# --- 3. CORE HEALTH ALGORITHMS ---
def calculate_dynamic_target(user_data):
    """
    Implements the Mifflin-St Jeor Equation with Real-Time Activity Adjustments.
    Calculates the 'Fuel Target' based on biometric data and daily movement.
    """
    # Extract current metrics
    weight_kg = float(user_data.get('weight', 70))
    height_cm = float(user_data.get('height_cm', 170))
    age_years = int(user_data.get('age', 30))
    
    # Calculate Base Metabolic Rate (BMR)
    # Formula: (10 × weight) + (6.25 × height) - (5 × age) + 5
    bmr_base = (10 * weight_kg) + (6.25 * height_cm) - (5 * age_years) + 5
    
    # Apply Goal-Specific Offsets
    user_goal = user_data.get('goal', 'Longevity')
    if user_goal == "Fat Loss":
        goal_offset = -500
    elif user_goal == "Muscle Build":
        goal_offset = 350
    else:
        goal_offset = 0
        
    # Apply Dynamic Step Bonus (0.04 kcal burned per step)
    daily_steps = user_data.get('daily_steps', 0)
    step_bonus = daily_steps * 0.04
    
    # Final Dynamic Calculation
    total_target = int(bmr_base + goal_offset + step_bonus)
    return total_target

# --- 4. AI AGENT & NLP COMMAND CENTER ---
def handle_chat():
    """Processes user chat and automates metric logging via Natural Language."""
    user_input = st.session_state.chat_input_box
    if not user_input: 
        return
    
    user_data = st.session_state.user_data
    username = st.session_state.logged_in_user
    
    # Record user message in history
    user_data['chat_history'].insert(0, {"role": "user", "content": user_input})
    
    # Initialize Pulse AI Coach
    health_coach = Agent(
        model=Groq(id="llama-3.3-70b-versatile", api_key=my_groq_key), 
        instructions=[
            f"You are Pulse AI, the elite digital health coach for {user_data.get('name')}.",
            "You have the power to update health metrics using the following syntax:",
            "If the user mentions food or calories, reply with: UPDATE: calories [value].",
            "If the user mentions steps or walking, reply with: UPDATE: steps [value].",
            "If the user mentions weight or scale results, reply with: UPDATE: weight [value].",
            "If the user mentions fatigue, sleep, or recovery, reply with: UPDATE: recovery [value].",
            "Always provide specific, data-backed health advice in addition to commands."
        ]
    )
    
    # Execute AI reasoning
    ai_response = health_coach.run(user_input).content
    
    # Command Parsing Engine
    if "UPDATE:" in ai_response:
        numbers_found = re.findall(r'\d+\.?\d*', ai_response)
        if numbers_found:
            extracted_val = float(numbers_found[0])
            
            if "calories" in ai_response.lower():
                user_data['daily_calories'] += int(extracted_val)
            elif "steps" in ai_response.lower():
                user_data['daily_steps'] += int(extracted_val)
            elif "recovery" in ai_response.lower():
                # Bound recovery between 0 and 100
                user_data['readiness'] = min(100, max(0, int(extracted_val)))
            elif "weight" in ai_response.lower():
                user_data['weight'] = extracted_val
                # Recalculate BMI on weight change
                user_data['bmi'] = round(extracted_val / ((user_data['height_cm'] / 100)**2), 1)
                user_data['weight_log'] = add_trend_entry(user_data['weight_log'], extracted_val)
    else:
        # Save standard AI response to history
        user_data['chat_history'].insert(1, {"role": "assistant", "content": ai_response})
    
    # Save session state
    save_user_data(username, user_data)
    st.session_state.chat_input_box = ""

# --- 5. PREMIUM UI THEMING & CSS ---
st.set_page_config(page_title="Pulse AI", page_icon="⚡", layout="wide")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Global App Background */
    .stApp { background-color: #FAFAFA; color: #1C1C1E; font-family: 'Inter', sans-serif; }
    
    /* Header Typography */
    h1 { font-weight: 700; letter-spacing: -0.5px; color: #1C1C1E; margin-bottom: 25px; }
    
    /* KPI Command Center Cards */
    .pulse-card {
        background: #FFFFFF; border-radius: 24px; padding: 22px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.03); border: 1px solid rgba(0,0,0,0.04);
        height: 165px; display: flex; flex-direction: column; justify-content: space-between;
    }
    .metric-title { color: #8E8E93; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; }
    .metric-value { color: #111111; font-size: 2.2rem; font-weight: 700; line-height: 1; }
    .metric-subtext { color: #8E8E93; font-size: 0.8rem; margin-top: 5px; }
    
    /* Modern Progress Bars */
    .progress-bg { background: #F2F2F7; border-radius: 10px; height: 8px; width: 100%; margin-top: 10px; overflow: hidden; }
    .progress-fill { height: 100%; border-radius: 10px; transition: width 0.8s ease-in-out; }
    
    /* Sidebar Components */
    .sidebar-container { background: #FFFFFF; border-radius: 16px; padding: 18px; border: 1px solid #E5E5EA; margin-bottom: 20px; }
    
    /* Tab Navigation Styling */
    .stTabs [aria-selected="true"] { background: #111111 !important; color: #FFFFFF !important; border-radius: 12px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 6. APPLICATION ROUTING & VIEW LOGIC ---
def main():
    if 'logged_in_user' not in st.session_state:
        st.session_state.logged_in_user = None

    # --- PHASE 1: AUTHENTICATION ---
    if st.session_state.logged_in_user is None:
        st.title("⚡ Pulse AI — Digital Health")
        tab_login, tab_signup = st.tabs(["Secure Login", "Create Profile"])
        
        with tab_login:
            user_in = st.text_input("Username").lower().strip()
            pass_in = st.text_input("Password", type="password")
            if st.button("Unlock Dashboard", use_container_width=True):
                existing_data = load_user_data(user_in)
                if existing_data and existing_data.get("password") == pass_in:
                    st.session_state.logged_in_user = user_in
                    st.session_state.user_data = existing_data
                    st.rerun()
                else:
                    st.error("Invalid credentials. Access Denied.")
        
        with tab_signup:
            user_new = st.text_input("New Username").lower().strip()
            pass_new = st.text_input("New Password", type="password")
            if st.button("Register Digital Health Account", use_container_width=True):
                if user_new and pass_new:
                    if os.path.exists(get_user_file(user_new)):
                        st.error("Username already registered.")
                    else:
                        save_user_data(user_new, {"password": pass_new, "onboarded": False})
                        st.success("Account Secured. Proceed to Login.")
        return

    # --- PHASE 2: ONBOARDING & BIO-SYNTHESIS ---
    user_data = st.session_state.user_data
    username = st.session_state.logged_in_user

    if not user_data.get("onboarded"):
        st.title(f"Bio-Digital Protocol for {username.capitalize()}")
        with st.form("onboarding_suite"):
            col_left, col_right = st.columns(2)
            name_val = col_left.text_input("Legal Name")
            age_val = col_left.number_input("Biological Age", 18, 100, 28)
            ft_val = col_left.selectbox("Height (Feet)", [4, 5, 6, 7], index=1)
            in_val = col_left.selectbox("Height (Inches)", list(range(12)), index=9)
            
            weight_val = col_right.number_input("Current Weight (kg)", 40.0, 200.0, 70.0)
            goal_val = col_right.selectbox("Protocol Goal", ["Fat Loss", "Muscle Build", "Longevity", "Performance"])
            diet_val = col_right.selectbox("Dietary Foundation", ["Vegetarian", "Non-vegetarian", "Keto", "Vegan", "Paleo"])
            
            if st.form_submit_button("Synthesize Health Plan"):
                with st.spinner("AI is calculating your metabolic protocols..."):
                    cm_total = (ft_val * 30.48) + (in_val * 2.54)
                    groq_model = Groq(id="llama-3.3-70b-versatile", api_key=my_groq_key)
                    
                    # AI-generated custom plans
                    diet_response = Agent(model=groq_model).run(f"Detailed {diet_val} plan for {goal_val}").content
                    workout_response = Agent(model=groq_model).run(f"Detailed training plan for {goal_val}").content
                    
                    user_data.update({
                        "onboarded": True,
                        "name": name_val, "age": age_val, "weight": weight_val, "height_cm": cm_total,
                        "goal": goal_val, "diet_plan": diet_response, "fit_plan": workout_response,
                        "readiness": 85, "daily_steps": 0, "daily_calories": 0,
                        "bmi": round(weight_val / ((cm_total/100)**2), 1),
                        "chat_history": [],
                        "weight_log": [{"date": datetime.now().strftime("%Y-%m-%d"), "value": weight_val}]
                    })
                    save_user_data(username, user_data)
                    st.rerun()
        return

    # --- PHASE 3: SIDEBAR CONTROL CENTER ---
    with st.sidebar:
        st.markdown(f"### 👤 Profile: {user_data.get('name')}")
        st.markdown("<div class='sidebar-container'>", unsafe_allow_html=True)
        st.write("📈 **Metric Log**")
        
        # Immediate inputs for dashboard sync
        in_weight = st.number_input("Body Mass (kg)", value=float(user_data['weight']), step=0.1)
        in_recovery = st.slider("Readiness Score %", 0, 100, int(user_data.get('readiness', 85)))
        in_steps = st.number_input("Log Steps", value=0, step=500)
        in_cals = st.number_input("Log Calories", value=0, step=100)
        
        if st.button("Sync Vitality Data", use_container_width=True):
            user_data['weight'] = in_weight
            user_data['readiness'] = in_recovery
            user_data['daily_steps'] += in_steps
            user_data['daily_calories'] += in_cals
            user_data['bmi'] = round(in_weight / ((user_data['height_cm'] / 100)**2), 1)
            user_data['weight_log'] = add_trend_entry(user_data['weight_log'], in_weight)
            save_user_data(username, user_data)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        if st.button("Log Out Session", use_container_width=True):
            st.session_state.logged_in_user = None
            st.rerun()
            
        if st.button("Reset Health Protocol", use_container_width=True):
            user_data["onboarded"] = False
            save_user_data(username, user_data)
            st.rerun()

    # --- PHASE 4: 5-TILE KPI COMMAND CENTER ---
    st.markdown(f"<h1>{user_data['name']}'s Intelligence Dashboard</h1>", unsafe_allow_html=True)
    
    current_fuel_cap = calculate_dynamic_target(user_data)
    col_1, col_2, col_3, col_4, col_5 = st.columns(5)
    
    with col_1: # Recovery Tile
        readiness_score = user_data.get('readiness', 85)
        # Dynamic color mapping for recovery status
        bar_color = "#34C759" if readiness_score > 75 else "#FFCC00" if readiness_score > 45 else "#FF3B30"
        st.markdown(f"""
            <div class='pulse-card'>
                <span class='metric-title'>Recovery</span>
                <span class='metric-value'>{readiness_score}%</span>
                <div class='progress-bg'><div class='progress-fill' style='width:{readiness_score}%; background:{bar_color};'></div></div>
            </div>
        """, unsafe_allow_html=True)

    with col_2: # Step Counter Tile
        actual_steps = user_data.get('daily_steps', 0)
        goal_step_pct = min(100, (actual_steps / 10000) * 100)
        st.markdown(f"""
            <div class='pulse-card'>
                <span class='metric-title'>Total Steps</span>
                <span class='metric-value'>{actual_steps:,}</span>
                <div class='progress-bg'><div class='progress-fill' style='width:{goal_step_pct}%; background:#007AFF;'></div></div>
            </div>
        """, unsafe_allow_html=True)

    with col_3: # BMI Calculation Tile
        bmi_current = user_data.get('bmi', 22.0)
        st.markdown(f"""
            <div class='pulse-card'>
                <span class='metric-title'>BMI Index</span>
                <span class='metric-value'>{bmi_current}</span>
                <span class='metric-subtext'>Relative Body Mass</span>
            </div>
        """, unsafe_allow_html=True)

    with col_4: # Dynamic Fuel Tile
        actual_cals = user_data.get('daily_calories', 0)
        fuel_consumption_pct = min(100, (actual_cals / current_fuel_cap) * 100)
        st.markdown(f"""
            <div class='pulse-card'>
                <span class='metric-title'>Fuel Intake</span>
                <span class='metric-value'>{actual_cals} <small style='font-size:14px; color:#8E8E93;'>/ {current_fuel_cap}</small></span>
                <div class='progress-bg'><div class='progress-fill' style='width:{fuel_consumption_pct}%; background:#FF9500;'></div></div>
            </div>
        """, unsafe_allow_html=True)

    with col_5: # Protocol Goal Tile
        display_goal = user_data.get('goal', 'LONGEVITY').upper()
        st.markdown(f"""
            <div class='pulse-card'>
                <span class='metric-title'>Active Goal</span>
                <span class='metric-value' style='font-size:1.1rem;'>{display_goal}</span>
                <span class='metric-subtext'>AI Optimized Strategy</span>
            </div>
        """, unsafe_allow_html=True)

    # --- PHASE 5: INTELLIGENCE TABS ---
    t_nutrition, t_training, t_trends, t_coach = st.tabs(["🥗 NUTRITION", "🏋️ TRAINING", "📈 TRENDS", "💬 SMART COACH"])
    
    with t_nutrition: 
        st.markdown("### Personalized Metabolic Diet Plan")
        st.markdown(f"<div style='background:white; padding:35px; border-radius:24px; border:1px solid #EEE; color:#1C1C1E; line-height:1.7;'>{user_data['diet_plan']}</div>", unsafe_allow_html=True)
    
    with t_training: 
        st.markdown("### Precision Strength & Performance Routine")
        st.markdown(f"<div style='background:white; padding:35px; border-radius:24px; border:1px solid #EEE; color:#1C1C1E; line-height:1.7;'>{user_data['fit_plan']}</div>", unsafe_allow_html=True)
    
    with t_trends:
        st.markdown("### Weight Trajectory Analysis")
        historical_df = pd.DataFrame(user_data['weight_log']).set_index('date')
        st.line_chart(historical_df, color="#007AFF")
            
    with t_coach:
        st.markdown("### Communicate with Pulse AI")
        st.text_input("Enter command or question...", key="chat_input_box", on_change=handle_chat, placeholder="e.g. 'I just ate 400 calories' or 'Set recovery to 90%'")
        st.markdown("---")
        for message_obj in user_data['chat_history']:
            with st.chat_message(message_obj["role"]):
                st.markdown(message_obj["content"])

if __name__ == "__main__":
    main()