import streamlit as st
import pandas as pd
from api_client import APIClient
from ai_service import AIService
from config import load_token, clear_token

# Page setup
st.set_page_config(
    page_title="Workout Tracker AI",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded"
)

api = APIClient()

token = load_token()
is_logged_in = token is not None

with st.sidebar:
    st.title("🏋️ Workout Tracker AI")
    st.write("Log workouts naturally & get smart coaching.")
    st.divider()
    
    if not is_logged_in:
        tab_login, tab_register = st.tabs(["Login", "Register"])
        
        with tab_login:
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.button("Login", use_container_width=True):
                if api.login(email, password):
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
        
        with tab_register:
            reg_email = st.text_input("Email", key="reg_email")
            reg_password = st.text_input("Password", type="password", key="reg_pass")
            if st.button("Register Account", use_container_width=True):
                try:
                    api.register(reg_email, reg_password)
                    st.success("Account registered! Please log in.")
                except Exception as e:
                    st.error(f"Registration failed: {e}")
    else:
        st.success("Authorized Session Active")
        if st.button("Logout", use_container_width=True):
            clear_token()
            st.rerun()

if not is_logged_in:
    st.info("👋 Please log in or register via the sidebar to access your workout portal.")
else:
    # Set up dashboard tabs
    tab_log, tab_history, tab_coach = st.tabs([
        "📝 Log Workout (AI)",
        "📅 Workout History",
        "🧠 AI Personal Coach"
    ])
    
    with tab_log:
        st.header("Log with Natural Language")
        st.write("Describe your session like a journal entry. Gemini will map it to database exercises.")
        
        raw_notes = st.text_area(
            "What did you train today?",
            placeholder="e.g., Did 3 sets of Bench Press with 10 reps at 135 lbs, then 3 sets of Squats with 8 reps at 225 lbs.",
            height=120
        )
        
        if st.button("Parse & Save Workout", type="primary"):
            if not raw_notes.strip():
                st.warning("Please type out your workout details first.")
            else:
                with st.spinner("Analyzing log with Gemini..."):
                    try:
                        available_exercises = api.get_exercises()
                        if not available_exercises:
                            st.error("Could not fetch database exercise references.")
                            st.stop()
                        
                        ai = AIService()
                        parsed = ai.parse_workout_text(raw_notes, available_exercises)
                        
                        workout_name = parsed.get("workout_name", "AI Parsed Workout")
                        sets = parsed.get("sets", [])
                        
                        if not sets:
                            st.warning(
                                "Gemini couldn't identify any matching exercises/sets. Double-check your database list.")
                        else:
                            created_workout = api.create_workout(name=workout_name)
                            workout_id = created_workout["id"]
                            
                            for s in sets:
                                api.add_set(
                                    workout_id=workout_id,
                                    exercise_id=s["exercise_id"],
                                    reps=s["reps"],
                                    weight=s["weight"],
                                    set_order=s["set_order"]
                                )
                            
                            st.balloons()
                            st.success(
                                f"Successfully saved **'{workout_name}'** (ID #{workout_id}) with {len(sets)} sets!")
                    except Exception as e:
                        st.error(f"Failed to log workout: {e}")
    
    with tab_history:
        col_hist, col_ex = st.columns([2, 1])
        
        with col_hist:
            st.subheader("Your Workout Logs")
            try:
                workouts = api.get_workouts()
                if workouts:
                    # Parse dates nicely into a clean table
                    df_workouts = pd.DataFrame(workouts)
                    df_display = df_workouts[["id", "name", "created_at"]].copy()
                    df_display.columns = ["Workout ID", "Workout Name", "Logged Date"]
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                else:
                    st.info("You haven't logged any workouts yet!")
            except Exception as e:
                st.error(f"Error loading history: {e}")
        
        with col_ex:
            st.subheader("Available Database Exercises")
            try:
                exercise_list = api.get_exercises()
                if exercise_list:
                    df_ex = pd.DataFrame(exercise_list)
                    df_ex_display = df_ex[["id", "name", "category"]].copy()
                    df_ex_display.columns = ["ID", "Exercise Name", "Category"]
                    st.dataframe(df_ex_display, use_container_width=True, hide_index=True)
                else:
                    st.info("No exercise reference types set up in the DB.")
            except Exception as e:
                st.error(f"Error loading exercises: {e}")
    
    with tab_coach:
        st.header("🧠 AI Fitness Coach Insights")
        st.write(
            "Let Gemini evaluate your progression targets, weekly volume, and provide your next actionable progressive overload goals.")
        
        if st.button("Generate Training Analysis", type="primary"):
            with st.spinner("Analyzing historical patterns..."):
                try:
                    history_data = api.get_workouts()
                    if not history_data:
                        st.info("Log a few workouts first to unlock progressive coaching!")
                    else:
                        ai = AIService()
                        coaching_markdown = ai.get_coaching_advice(history_data)
                        st.markdown(coaching_markdown)
                except Exception as e:
                    st.error(f"Could not retrieve advice: {e}")