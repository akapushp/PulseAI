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
    # Keep last 14 days for the trend chart
    return log[-14:] 

# --- 3. DYNAMIC TARGET CALCULATOR ---
def calculate_dynamic_target(user_data):
    # Mifflin-St Jeor Equation:
    # BMR = (10 × weight in kg) + (6.25 × height in cm) - (5 × age) + 5
    weight = float(user_data.get('weight', 70))
    height = float(user_data.get('height_cm', 170))
    age = int(user_data.get('age', 30))
    
    bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    
    # Goal Adjustment
    goal = user_data.get('goal', 'Longevity')
    if goal == "Fat Loss":
        offset = -500
    elif goal == "Muscle Build":
        offset = 300
    else:
        offset = 0
        
    # Activity Bonus: ~0.04 kcal burned per step
    step_bonus = user_data.get('daily_steps', 0) * 0.04
    
    return int(bmr + offset + step_bonus)

# --- 4. CHAT CALLBACK ---
def handle_chat():
    prompt = st.session_state.chat_input_box
    if not prompt: return
    
    user_data = st.session_state.user_data
    username = st.session_state.logged_in_user
    
    # Track interaction
    user_data['chat_history'].insert(0, {"role": "user", "content": prompt})
    
    coach = Agent(
        model=Groq(id="llama-3.3-70b-versatile", api_key=my_groq_key), 
        instructions=[
            f"You are Pulse AI, the digital health coach for {user_data.get('name')}.",
            "If the user mentions food or calories, reply with 'UPDATE: calories [number]'.",
            "If the user mentions steps, reply with 'UPDATE: steps [number]'.",
            "If the user mentions weight, reply with 'UPDATE: weight [number]'.",
            "Otherwise, provide elite, concise health and performance coaching."
        ]
    )
    
    response = coach.run(prompt).content
    
    # Logic to parse AI commands
    if "UPDATE:" in response:
        nums = re.findall(r'\d+\.?\d*', response)
        if nums:
            val = float(nums[0])
            if "calories" in response.lower():
                user_data['daily_calories'] += int(val)
            elif "steps" in response.lower():
                user_data['daily_steps'] += int(val)
            elif "weight" in response.lower():
                user_data['weight'] = val
                user_data['bmi'] = round(val / ((user_data['height_cm'] / 100)**2), 1)
                user_data['weight_log'] = add_trend_entry(user_data['weight_log'], val)
    else:
        user_data['chat_history'].insert(1, {"role": "assistant", "content": response})
    
    save_user_data(username, user_data)
    st.session_state.chat_input_box = ""

# --- 5. UI STYLING ---
st.set_page_config(page_title="Pulse AI", page_icon="⚡", layout="wide")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp { background-color: #FAFAFA; color: #1C1C1E; font-family: 'Inter', sans-serif; }
    h1 { font-weight: 700; letter-spacing: -0.5px; color: #1C1C1E; }
    .pulse-card {
        background: #FFFFFF; border-radius: 24px; padding: 22px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.03); border: 1px solid rgba(0,0,0,0.04);
        height: 160px; display: flex; flex-direction: column; justify-content: space-between;
    }
    .metric-title { color: #8E8E93; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; }
    .metric-value { color: #111111; font-size: 2rem; font-weight: 700; line-height: 1; }
    .progress-bg { background: #F2F2F7; border-radius: 10px; height: 8px; width: 100%; margin-top: 10px; overflow: hidden; }
    .progress-fill { height: 100%; border-radius: 10px; transition: width 0.6s ease; }
    .sidebar-box { background: #FFFFFF; border-radius: 16px; padding: 16px; border: 1px solid #E5E5EA; margin-bottom: 15px; }
    .stTabs [aria-selected="true"] { background: #111111 !important; color: #FFFFFF !important; border-radius: 12px !important; }
    </style>
    """, unsafe_allow_html=True)

def main():
    if 'logged_in_user' not in st.session_state:
        st.session_state.logged_in_user = None

    # --- A. AUTHENTICATION ---
    if st.session_state.logged_in_user is None:
        st.title("⚡ Pulse AI — Digital Health")
        tab1, tab2 = st.tabs(["Login", "Create Account"])
        with tab1:
            u_login = st.text_input("Username").lower().strip()
            p_login = st.text_input("Password", type="password")
            if st.button("Sign In", use_container_width=True):
                data = load_user_data(u_login)
                if data and data.get("password") == p_login:
                    st.session_state.logged_in_user = u_login
                    st.session_state.user_data = data
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
        with tab2:
            u_signup = st.text_input("Choose Username").lower().strip()
            p_signup = st.text_input("Choose Password", type="password")
            if st.button("Create Account", use_container_width=True):
                if u_signup and p_signup:
                    if os.path.exists(get_user_file(u_signup)):
                        st.error("Username already taken.")
                    else:
                        save_user_data(u_signup, {"password": p_signup, "onboarded": False})
                        st.success("Account created! You can now login.")
        return

    user_data = st.session_state.user_data
    username = st.session_state.logged_in_user

    # --- B. ONBOARDING ---
    if not user_data.get("onboarded"):
        st.title(f"Configure Your Protocol, {username.capitalize()}")
        with st.form("onboarding_form"):
            col1, col2 = st.columns(2)
            name = col1.text_input("Full Name")
            age = col1.number_input("Age", 18, 100, 25)
            feet = col1.selectbox("Height (Feet)", [4, 5, 6, 7], index=1)
            inches = col1.selectbox("Height (Inches)", list(range(12)), index=9)
            
            weight = col2.number_input("Current Weight (kg)", 40.0, 200.0, 75.0)
            goal = col2.selectbox("Primary Goal", ["Fat Loss", "Muscle Build", "Longevity", "Strength"])
            diet = col2.selectbox("Dietary Preference", ["Vegetarian", "Non-vegetarian", "Keto", "Vegan"])
            
            if st.form_submit_button("Initialize AI Health Plan"):
                with st.spinner("Pulse AI is calculating your protocols..."):
                    h_cm = (feet * 30.48) + (inches * 2.54)
                    model = Groq(id="llama-3.3-70b-versatile", api_key=my_groq_key)
                    
                    # Generate protocols
                    diet_p = Agent(model=model).run(f"Create a {diet} meal plan for {goal}").content
                    fit_p = Agent(model=model).run(f"Create a workout routine for {goal}").content
                    
                    user_data.update({
                        "onboarded": True,
                        "name": name, "age": age, "weight": weight, "height_cm": h_cm,
                        "goal": goal, "diet_plan": diet_p, "fit_plan": fit_p,
                        "readiness": 100, "daily_steps": 0, "daily_calories": 0,
                        "bmi": round(weight / ((h_cm/100)**2), 1),
                        "chat_history": [],
                        "weight_log": [{"date": datetime.now().strftime("%Y-%m-%d"), "value": weight}]
                    })
                    save_user_data(username, user_data)
                    st.rerun()
        return

    # --- C. SIDEBAR ---
    with st.sidebar:
        st.markdown(f"### 👤 {user_data.get('name', 'User')}")
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        st.write("📈 **Manual Update**")
        new_w = st.number_input("Weight (kg)", value=float(user_data['weight']), step=0.1)
        new_s = st.number_input("Add Steps", value=0, step=500)
        new_c = st.number_input("Add Calories", value=0, step=100)
        
        if st.button("Sync Vitality Data", use_container_width=True):
            user_data['weight'] = new_w
            user_data['daily_steps'] += new_s
            user_data['daily_calories'] += new_c
            user_data['bmi'] = round(new_w / ((user_data['height_cm'] / 100)**2), 1)
            user_data['weight_log'] = add_trend_entry(user_data['weight_log'], new_w)
            save_user_data(username, user_data)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        if st.button("Logout", use_container_width=True):
            st.session_state.logged_in_user = None
            st.rerun()
            
        if st.button("🔄 Reset Health Profile", use_container_width=True):
            user_data["onboarded"] = False
            save_user_data(username, user_data)
            st.rerun()

    # --- D. DASHBOARD HEADER ---
    st.markdown(f"<h1>{user_data['name']}'s Digital Health</h1>", unsafe_allow_html=True)
    
    # --- E. 5 KPI TILES ---
    dyn_target = calculate_dynamic_target(user_data)
    k1, k2, k3, k4, k5 = st.columns(5)
    
    with k1: # Recovery
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Recovery</span><span class='metric-value'>{user_data['readiness']}%</span><div class='progress-bg'><div class='progress-fill' style='width:{user_data['readiness']}%; background:#34C759;'></div></div></div>", unsafe_allow_html=True)
    
    with k2: # Steps
        s_pct = min(100, (user_data['daily_steps'] / 10000) * 100)
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Steps</span><span class='metric-value'>{user_data['daily_steps']:,}</span><div class='progress-bg'><div class='progress-fill' style='width:{s_pct}%; background:#007AFF;'></div></div></div>", unsafe_allow_html=True)
    
    with k3: # BMI
        bmi_val = user_data['bmi']
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>BMI Index</span><span class='metric-value'>{bmi_val}</span><div style='color:#8E8E93; font-size:0.7rem;'>PROPORTIONAL WEIGHT</div></div>", unsafe_allow_html=True)
    
    with k4: # Fuel (Dynamic Target)
        f_pct = min(100, (user_data['daily_calories'] / dyn_target) * 100)
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Fuel Status</span><span class='metric-value'>{user_data['daily_calories']} <small style='font-size:14px; color:#8E8E93;'>/ {dyn_target}</small></span><div class='progress-bg'><div class='progress-fill' style='width:{f_pct}%; background:#FF9500;'></div></div></div>", unsafe_allow_html=True)
    
    with k5: # Goal Focus
        st.markdown(f"<div class='pulse-card'><span class='metric-title'>Focus</span><span class='metric-value' style='font-size:1.2rem;'>{user_data['goal'].upper()}</span><div style='color:#8E8E93; font-size:0.7rem;'>ACTIVE PROTOCOL</div></div>", unsafe_allow_html=True)

    # --- F. TABS ---
    t1, t2, t3, t4 = st.tabs(["🥗 NUTRITION", "🏋️ TRAINING", "📈 TRENDS", "💬 SMART COACH"])
    
    with t1: 
        st.markdown("### Personalized Nutrition Protocol")
        st.markdown(f"<div style='background:white; padding:25px; border-radius:24px; border:1px solid #EEE; color:#1C1C1E;'>{user_data['diet_plan']}</div>", unsafe_allow_html=True)
    
    with t2: 
        st.markdown("### Precision Training Plan")
        st.markdown(f"<div style='background:white; padding:25px; border-radius:24px; border:1px solid #EEE; color:#1C1C1E;'>{user_data['fit_plan']}</div>", unsafe_allow_html=True)
    
    with t3:
        st.markdown("### Weight Evolution")
        df = pd.DataFrame(user_data['weight_log']).set_index('date')
        st.line_chart(df)
            
    with t4:
        st.markdown("### Consult Smart Coach")
        st.text_input("Message Coach...", key="chat_input_box", on_change=handle_chat, placeholder="e.g. 'I just ran 5km' or 'Log 500 calories'")
        st.markdown("---")
        for msg in user_data['chat_history']:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

if __name__ == "__main__":
    main()