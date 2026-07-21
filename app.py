import streamlit as st
import pandas as pd
from ai_service import AIService
import httpx, time, os, psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash

query_params = st.query_params
if "ping" in query_params:
    st.write("OK")
    st.stop()

def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        st.error("DATABASE_URL environment variable is missing on Render!")
        st.stop()
    retries = 3
    for attempt in range(retries):
        try:
            return psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        except Exception as e:
            if attempt == retries - 1:
                raise e
            time.sleep(3)


# Page setup
st.set_page_config(
    page_title="Workout Tracker AI",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded"
)

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_id" not in st.session_state:
    st.session_state["user_id"] = None

is_logged_in = st.session_state["logged_in"]

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
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, password FROM users WHERE email = %s;", (email,))
                    user = cursor.fetchone()
                    cursor.close()
                    conn.close()
                    
                    if user and check_password_hash(user["password"], password):
                        st.session_state["logged_in"] = True
                        st.session_state["user_id"] = user["id"]
                        st.success("Logged in successfully!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")
                except Exception as e:
                    st.error(f"Login error: {e}")
        
        with tab_register:
            reg_email = st.text_input("Email", key="reg_email")
            reg_password = st.text_input("Password", type="password", key="reg_pass")
            if st.button("Register Account", use_container_width=True):
                if not reg_email or not reg_password:
                    st.warning("Please fill out both fields.")
                else:
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        hashed_password = generate_password_hash(reg_password)
                        
                        cursor.execute(
                            "INSERT INTO users (email, password) VALUES (%s, %s);",
                            (reg_email, hashed_password)
                        )
                        conn.commit()
                        cursor.close()
                        conn.close()
                        st.success("Account registered! Please log in inside the Login tab.")
                    except psycopg2.errors.UniqueViolation:
                        st.error("An account with this email already exists.")
                    except Exception as e:
                        st.error(f"Registration failed: {e}")
    else:
        st.success("Authorized Session Active")
        if st.button("Logout", use_container_width=True):
            st.session_state["logged_in"] = False
            st.session_state["user_id"] = None
            st.rerun()

if not is_logged_in:
    st.info("👋 Please log in or register via the sidebar to access your workout portal.")
else:
    current_user_id = st.session_state["user_id"]
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
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT id, name, category FROM exercises;")
                        available_exercises = cursor.fetchall()
                        
                        if not available_exercises:
                            st.error(
                                "Could not fetch database exercise references. Ensure your exercises table is seeded.")
                            st.stop()
                        
                        ai = AIService()
                        parsed = ai.parse_workout_text(raw_notes, available_exercises)
                        
                        workout_name = parsed.get("workout_name", "AI Parsed Workout")
                        sets = parsed.get("sets", [])
                        
                        if not sets:
                            st.warning("Gemini couldn't identify any matching exercises/sets.")
                        else:
                            cursor.execute(
                                "INSERT INTO workouts (user_id, name) VALUES (%s, %s) RETURNING id;",
                                (current_user_id, workout_name)
                            )
                            workout_id = cursor.fetchone()["id"]
                            
                            for s in sets:
                                cursor.execute(
                                    """INSERT INTO sets (workout_id, exercise_id, reps, weight, set_order)
                                       VALUES (%s, %s, %s, %s, %s);""",
                                    (workout_id, s["exercise_id"], s["reps"], s["weight"], s["set_order"])
                                )
                            
                            conn.commit()
                            st.balloons()
                            st.success(
                                f"Successfully saved **'{workout_name}'** (ID #{workout_id}) with {len(sets)} sets!")
                        
                        cursor.close()
                        conn.close()
                    except Exception as e:
                        st.error(f"Failed to log workout: {e}")
    
    with tab_history:
        col_hist, col_ex = st.columns([2, 1])
        
        with col_hist:
            st.subheader("Your Workout Logs")
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, name, created_at FROM workouts WHERE user_id = %s ORDER BY created_at DESC;",
                    (current_user_id,)
                )
                workouts = cursor.fetchall()
                cursor.close()
                conn.close()
                
                if workouts:
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
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, category FROM exercises ORDER BY name ASC;")
                exercise_list = cursor.fetchall()
                cursor.close()
                conn.close()
                
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
        st.write("Let Gemini evaluate your progression targets and provide progressive overload goals.")
        
        if st.button("Generate Training Analysis", type="primary"):
            with st.spinner("Analyzing historical patterns..."):
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, name, created_at FROM workouts WHERE user_id = %s;", (current_user_id,))
                    history_data = cursor.fetchall()
                    cursor.close()
                    conn.close()
                    
                    if not history_data:
                        st.info("Log a few workouts first to unlock progressive coaching!")
                    else:
                        formatted_history = []
                        for row in history_data:
                            row_dict = dict(row)
                            if "created_at" in row_dict and row_dict["created_at"]:
                                row_dict["created_at"] = str(row_dict["created_at"])
                            formatted_history.append(row_dict)
                        
                        ai = AIService()
                        coaching_markdown = ai.get_coaching_advice(formatted_history)
                        st.markdown(coaching_markdown)
                except Exception as e:
                    st.error(f"Could not retrieve advice: {e}")