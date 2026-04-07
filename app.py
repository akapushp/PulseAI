import streamlit as st
import os
import json
import pandas as pd
import re
from datetime import datetime
from agno.agent import Agent
from agno.models.groq import Groq

# ==============================================================================
# 1. SYSTEM CORE & SECURE CONFIGURATION
# ==============================================================================
# We use st.secrets for production-grade security. 
# This ensures API keys are never hardcoded in the script.
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception as e:
    st.error("🚨 CONFIGURATION ERROR: GROQ_API_KEY is missing from Streamlit Secrets.")
    st.info("Please add your key to .streamlit/secrets.toml or the Streamlit Cloud dashboard.")
    st.stop()

# ==============================================================================
# 2. DATA PERSISTENCE LAYER (JSON ENGINE)
# ==============================================================================
def get_user_database_path(username):
    """Generates a standardized filename for user data persistence."""
    clean_username = username.lower().strip()
    return f"db_user_{clean_username}.json"

def save_user_state(username, data_object):
    """Writes the current session state to a permanent JSON file."""
    file_path = get_user_database_path(username)
    with open(file_path, "w", encoding='utf-8') as database_file:
        json.dump(data_object, database_file, indent=4)

def load_user_state(username):
    """Retrieves user data from storage. Returns None if user does not exist."""
    file_path = get_user_database_path(username)
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding='utf-8') as database_file:
                return json.load(database_file)
        except (json.JSONDecodeError, IOError):
            return None
    return None

def update_weight_trajectory(weight_log, new_weight_value):
    """
    Manages a 14-day rolling window of weight data for trend analysis.
    Ensures that only one data point exists per calendar day.
    """
    current_date_string = datetime.now().strftime("%Y-%m-%d")
    
    # Check if we already have an entry for today
    existing_entry_found = False
    for entry in weight_log:
        if entry['date'] == current_date_string:
            entry['value'] = float(new_weight_value)
            existing_entry_found = True
            break
            
    if not existing_entry_found:
        weight_log.append({
            "date": current_date_string, 
            "value": float(new_weight_value)
        })
    
    # Prune list to keep only the last 14 entries for the UI chart
    return weight_log[-14:] 

# ==============================================================================
# 3. BIOMETRIC ALGORITHMS
# ==============================================================================
def calculate_metabolic_targets(user_metadata):
    """
    Implements the Mifflin-St Jeor Equation to determine Basal Metabolic Rate (BMR).
    Then applies activity bonuses and goal-specific caloric offsets.
    """
    # 1. Extract and cast variables safely
    current_w = float(user_metadata.get('weight', 70))
    current_h = float(user_metadata.get('height_cm', 175))
    current_a = int(user_metadata.get('age', 30))
    
    # 2. Base BMR Calculation
    # Formula: (10 × weight_kg) + (6.25 × height_cm) - (5 × age) + 5
    bmr_result = (10 * current_w) + (6.25 * current_h) - (5 * current_a) + 5
    
    # 3. Apply Goal Offset
    target_goal = user_metadata.get('goal', 'Longevity')
    if target_goal == "Fat Loss":
        net_offset = -500
    elif target_goal == "Muscle Build":
        net_offset = 350
    else:
        net_offset = 0
        
    # 4. Activity Bonus (Thermal Effect of Activity)
    # Estimate: ~0.04 calories burned per step
    step_count = user_metadata.get('daily_steps', 0)
    activity_bonus = step_count * 0.04
    
    # 5. Final Synthesis
    calculated_fuel_target = int(bmr_result + net_offset + activity_bonus)
    return calculated_fuel_target

# ==============================================================================
# 4. MULTI-AGENT ORCHESTRATION & NLP
# ==============================================================================
def process_agent_interaction():
    """
    The 'Brain' of Pulse AI. Intercepts chat messages, uses Groq-powered agents
     to extract health data, and updates the system state automatically.
    """
    raw_user_prompt = st.session_state.chat_input_box
    if not raw_user_prompt:
        return
    
    current_session_data = st.session_state.user_data
    current_username = st.session_state.logged_in_user
    
    # Log user message to session history
    current_session_data['chat_history'].insert(0, {
        "role": "user", 
        "content": raw_user_prompt
    })
    
    # Initialize the Agno/Groq Agent
    # This agent is instructed to look for 'logging' intent.
    health_intelligence_agent = Agent(
        model=Groq(id="llama-3.3-70b-versatile", api_key=GROQ_API_KEY), 
        instructions=[
            f"You are the Pulse AI High-Performance Coach for {current_session_data.get('name')}.",
            "Your primary goal is to provide elite health advice and manage the user's data.",
            "CRITICAL: If the user provides a numeric health update, you MUST reply with a command.",
            "COMMAND FORMATS:",
            "- UPDATE: calories [number] (for food/meals)",
            "- UPDATE: steps [number] (for movement)",
            "- UPDATE: weight [number] (for body mass)",
            "- UPDATE: recovery [number] (for readiness/sleep/fatigue)",
            "Always follow the command with a 1-sentence supportive response."
        ]
    )
    
    # Execute Agent Reasoning
    agent_execution_result = health_intelligence_agent.run(raw_user_prompt)
    ai_generated_text = agent_execution_result.content
    
    # Command Parsing Logic (Regex extraction)
    if "UPDATE:" in ai_generated_text:
        extracted_numbers = re.findall(r'\d+\.?\d*', ai_generated_text)
        if extracted_numbers:
            parsed_value = float(extracted_numbers[0])
            lowercase_response = ai_generated_text.lower()
            
            if "calories" in lowercase_response:
                current_session_data['daily_calories'] += int(parsed_value)
            elif "steps" in lowercase_response:
                current_session_data['daily_steps'] += int(parsed_value)
            elif "recovery" in lowercase_response:
                current_session_data['readiness'] = min(100, max(0, int(parsed_value)))
            elif "weight" in lowercase_response:
                current_session_data['weight'] = parsed_value
                # Recalculate BMI and update weight trend log
                h_m = current_session_data['height_cm'] / 100
                current_session_data['bmi'] = round(parsed_value / (h_m * h_m), 1)
                current_session_data['weight_log'] = update_weight_trajectory(
                    current_session_data['weight_log'], 
                    parsed_value
                )
    
    # Append the assistant's response to the history
    current_session_data['chat_history'].insert(1, {
        "role": "assistant", 
        "content": ai_generated_text
    })
    
    # Commit changes to database
    save_user_state(current_username, current_session_data)
    st.session_state.chat_input_box = ""

# ==============================================================================
# 5. HIGH-FIDELITY CSS (ASK-MYDOCS STYLE)
# ==============================================================================
st.set_page_config(page_title="Pulse AI | Digital Health", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    /* Import Inter for that premium Vercel aesthetic */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Root App Background - Clean Minimalist White */
    .stApp {
        background-color: #FFFFFF;
        color: #111111;
        font-family: 'Inter', sans-serif;
    }
    
    /* Style Chat Bubbles to match Ask-MyDocs */
    .stChatMessage {
        background-color: #FFFFFF !important;
        border: 1px solid #F3F4F6 !important;
        border-radius: 12px !important;
        padding: 1.25rem !important;
        margin-bottom: 1.25rem !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
    }
    
    /* Sidebar Navigation Styling */
    section[data-testid="stSidebar"] {
        background-color: #FAFAFA !important;
        border-right: 1px solid #E5E7EB !important;
    }
    
    /* KPI Card Component for Sidebar */
    .kpi-container {
        border: 1px solid #E5E7EB;
        background-color: #FFFFFF;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    .kpi-header {
        font-size: 0.65rem;
        font-weight: 600;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .kpi-body {
        font-size: 1.25rem;
        font-weight: 700;
        color: #111111;
    }
    
    /* Clean Tab Navigation */
    .stTabs [aria-selected="true"] {
        background-color: #F3F4F6 !important;
        color: #111111 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }

    /* Input Bar Positioning */
    .stChatInputContainer {
        padding-bottom: 30px;
    }
    
    /* Hide default Streamlit elements for "Pure App" feel */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 6. MAIN APPLICATION FLOW
# ==============================================================================
def main():
    # 1. Initialize Authentication State
    if 'logged_in_user' not in st.session_state:
        st.session_state.logged_in_user = None

    # --- LANDING & AUTHENTICATION PHASE ---
    if st.session_state.logged_in_user is None:
        st.title("⚡ Pulse AI")
        st.markdown("##### The Multi-Agent Health Command Center")
        
        login_tab, signup_tab = st.tabs(["Secure Login", "Create Account"])
        
        with login_tab:
            auth_user = st.text_input("Username").lower().strip()
            auth_pass = st.text_input("Password", type="password")
            if st.button("Access Pulse Dashboard", use_container_width=True):
                db_record = load_user_state(auth_user)
                if db_record and db_record.get("password") == auth_pass:
                    st.session_state.logged_in_user = auth_user
                    st.session_state.user_data = db_record
                    st.rerun()
                else:
                    st.error("Authentication failed. Please verify credentials.")
        
        with signup_tab:
            new_user = st.text_input("Choose Username").lower().strip()
            new_pass = st.text_input("Choose Password", type="password")
            if st.button("Initialize New Profile", use_container_width=True):
                if new_user and new_pass:
                    if os.path.exists(get_user_database_path(new_user)):
                        st.error("Account identity already registered.")
                    else:
                        initial_config = {"password": new_pass, "onboarded": False}
                        save_user_state(new_user, initial_config)
                        st.success("Account created successfully. Please login.")
        return

    # --- USER CONTEXT ---
    user_state = st.session_state.user_data
    username = st.session_state.logged_in_user

    # --- ONBOARDING PHASE (Bio-Protocol Generation) ---
    if not user_state.get("onboarded"):
        st.markdown("### Protocol Configuration")
        st.write("We need to establish your biological baseline to calibrate the Pulse Agents.")
        
        with st.form("onboarding_matrix"):
            left, right = st.columns(2)
            u_name = left.text_input("Full Name")
            u_age = left.number_input("Biological Age", 18, 100, 28)
            u_height = left.number_input("Height (cm)", 100, 250, 175)
            
            u_weight = right.number_input("Current Weight (kg)", 40.0, 200.0, 75.0)
            u_goal = right.selectbox("Primary Directive", ["Fat Loss", "Muscle Build", "Longevity", "Performance"])
            u_diet = right.selectbox("Nutritional Preference", ["Vegetarian", "Vegan", "Keto", "Omnivore"])
            
            if st.form_submit_button("Synthesize Health Protocol"):
                with st.spinner("Multi-Agent Synthesis in progress..."):
                    groq_llm = Groq(id="llama-3.3-70b-versatile", api_key=GROQ_API_KEY)
                    # Agent 1: Nutrition Expert
                    diet_p = Agent(model=groq_llm).run(f"Create a high-performance {u_diet} plan for {u_goal}").content
                    # Agent 2: Exercise Physiologist
                    fit_p = Agent(model=groq_llm).run(f"Create an elite training routine for {u_goal}").content
                    
                    user_state.update({
                        "onboarded": True,
                        "name": u_name, "age": u_age, "weight": u_weight, "height_cm": u_height,
                        "goal": u_goal, "diet_plan": diet_p, "fit_plan": fit_p,
                        "readiness": 85, "daily_steps": 0, "daily_calories": 0,
                        "bmi": round(u_weight / ((u_height/100)**2), 1),
                        "chat_history": [],
                        "weight_log": [{"date": datetime.now().strftime("%Y-%m-%d"), "value": u_weight}]
                    })
                    save_user_state(username, user_state)
                    st.rerun()
        return

    # --- SIDEBAR (METADATA & KPI COMMANDS) ---
    with st.sidebar:
        st.markdown(f"#### 👤 {user_state['name']}")
        st.markdown(f"<p style='color:#6B7280; font-size:0.8rem;'>Protocol: {user_state['goal']}</p>", unsafe_allow_html=True)
        st.divider()
        
        # Calculate metabolic target for the Fuel KPI
        daily_fuel_goal = calculate_metabolic_targets(user_state)
        
        # Display KPIs in minimalist "Ask-MyDocs" Cards
        kpi_list = [
            ("Current Readiness", f"{user_state['readiness']}%"),
            ("Accumulated Steps", f"{user_state['daily_steps']:,}"),
            ("Caloric Intake", f"{user_state['daily_calories']} / {daily_fuel_goal}"),
            ("Body Mass Index", f"{user_state['bmi']}")
        ]
        
        for k_label, k_val in kpi_list:
            st.markdown(f"""
                <div class='kpi-container'>
                    <div class='kpi-header'>{k_label}</div>
                    <div class='kpi-body'>{k_val}</div>
                </div>
            """, unsafe_allow_html=True)
            
        st.divider()
        
        # Utility Controls
        if st.button("Reset Protocol", use_container_width=True):
            user_state["onboarded"] = False
            save_user_state(username, user_state)
            st.rerun()
            
        if st.button("Terminate Session", use_container_width=True):
            st.session_state.logged_in_user = None
            st.rerun()

    # --- MAIN STAGE (TABS: CHAT, PROTOCOLS, ANALYTICS) ---
    chat_view, protocol_view, trend_view = st.tabs(["💬 Intelligence Chat", "📋 Protocol Specs", "📈 Bio-Trends"])

    with chat_view:
        # Render the Message History
        for message in user_state['chat_history']:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Floating Input Bar
        st.chat_input(
            "Talk to Pulse AI... (e.g., 'Log 2500 steps' or 'I feel tired today')", 
            key="chat_input_box", 
            on_submit=process_agent_interaction
        )

    with protocol_view:
        tab_nut, tab_fit = st.tabs(["🥗 Nutrition Protocol", "🏋️ Training Protocol"])
        with tab_nut:
            st.markdown(f"<div style='line-height:1.6;'>{user_state['diet_plan']}</div>", unsafe_allow_html=True)
        with tab_fit:
            st.markdown(f"<div style='line-height:1.6;'>{user_state['fit_plan']}</div>", unsafe_allow_html=True)

    with trend_view:
        st.subheader("Body Mass Trajectory (14 Days)")
        # Convert weight log to DataFrame for high-fidelity charting
        df_trends = pd.DataFrame(user_state['weight_log']).set_index('date')
        st.line_chart(df_trends, color="#111111")

if __name__ == "__main__":
    main()