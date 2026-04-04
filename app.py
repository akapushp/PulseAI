import streamlit as st
import os
import json
import pandas as pd
import re
from datetime import datetime
from agno.agent import Agent
from agno.models.groq import Groq

# --- PROD CONFIG: USE STREAMLIT SECRETS ---
try:
    my_groq_key = st.secrets["GROQ_API_KEY"]
except:
    st.error("Missing GROQ_API_KEY in Secrets!")
    st.stop()

# --- DATABASE SIMULATION (PROD-READY) ---
# For a real web app, you'd link this to Supabase or MongoDB. 
# For Step 1, we use a naming convention: [username]_data.json
def get_user_file(username):
    return f"data_{username}.json"

def save_user_data(username, data):
    with open(get_user_file(username), "w") as f:
        json.dump(data, f, indent=4)

def load_user_data(username):
    filename = get_user_file(username)
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return None

# --- SHARED FUNCTIONS ---
def add_trend_entry(log, value):
    today = datetime.now().strftime("%Y-%m-%d")
    for entry in log:
        if entry['date'] == today:
            entry['value'] = value
            return log
    log.append({"date": today, "value": value})
    return log[-14:] 

def handle_chat():
    prompt = st.session_state.chat_input_box
    if not prompt: return
    
    user_data = st.session_state.user_data
    username = st.session_state.logged_in_user
    
    user_data['chat_history'].insert(0, {"role": "user", "content": prompt})
    
    coach = Agent(
        model=Groq(id="llama-3.3-70b-versatile", api_key=my_groq_key), 
        instructions=[f"Pulse Engine for {user_data['name']}. Log metrics as 'UPDATE: [type] [value]' or give 1-sentence tips."]
    )
    
    response = coach.run(prompt).content
    
    if "UPDATE:" in response:
        if "calories" in response.lower():
            val = re.findall(r'\d+', response)
            if val: user_data['daily_calories'] += int(val[0])
        elif "steps" in response.lower():
            val = re.findall(r'\d+', response)
            if val: user_data['daily_steps'] += int(val[0])
        save_user_data(username, user_data)
    else:
        user_data['chat_history'].insert(1, {"role": "assistant", "content": response})
        save_user_data(username, user_data)
    
    st.session_state.chat_input_box = ""

# --- UI APP ---
st.set_page_config(page_title="Pulse AI", page_icon="⚡", layout="wide")

# (Keep your existing CSS here)

def main():
    if 'logged_in_user' not in st.session_state:
        # --- LOGIN SCREEN ---
        st.title("⚡ Pulse AI Login")
        user_input = st.text_input("Username").lower().strip()
        pass_input = st.text_input("Password", type="password")
        
        col1, col2 = st.columns(2)
        if col1.button("Login / Sign Up"):
            if user_input and pass_input == "pulse2026": # Simple gatekeeper
                st.session_state.logged_in_user = user_input
                data = load_user_data(user_input)
                st.session_state.user_data = data
                st.rerun()
            else:
                st.error("Invalid credentials")
    else:
        # --- LOGGED IN DASHBOARD ---
        username = st.session_state.logged_in_user
        user_data = st.session_state.user_data
        
        if user_data is None:
            # (Show Onboarding flow if no file exists for this username)
            st.title(f"Welcome, {username}! Let's set up your profile.")
            # ... (Existing Onboarding Logic Here) ...
        else:
            # (Show full Dashboard Logic here as we built it)
            st.sidebar.write(f"Active Session: {username}")
            if st.sidebar.button("Logout"):
                del st.session_state.logged_in_user
                st.rerun()
            
            # (Dashboard tabs and logic go here)

if __name__ == "__main__":
    main()