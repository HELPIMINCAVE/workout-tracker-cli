import streamlit as st
import pandas as pd
from ai_service import AIService
import time
import os
import random
import string
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
import resend

# Initialize Resend API Key
resend.api_key = os.environ.get("RESEND_API_KEY")

# 1. Handle cron-job.org light ping rule
query_params = st.query_params
if "ping" in query_params:
    st.write("OK")
    st.stop()


# 2. Database Connection Helper
def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        st.error("DATABASE_URL environment variable is missing!")
        st.stop()
    retries = 3
    for attempt in range(retries):
        try:
            return psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        except Exception as e:
            if attempt == retries - 1:
                raise e
            time.sleep(2)


# Page setup
st.set_page_config(
    page_title="Workout Tracker AI",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State tracking
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_id" not in st.session_state:
    st.session_state["user_id"] = None

is_logged_in = st.session_state["logged_in"]

# Sidebar authentication layout
with st.sidebar:
    st.title("🏋️ Workout Tracker AI")
    st.write("Log workouts naturally & get smart coaching.")
    st.divider()
    
    if not is_logged_in:
        tab_login, tab_register, tab_reset = st.tabs(["Login", "Register", "Reset Password"])
        
        # --- TAB 1: LOGIN ---
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
        
        # --- TAB 2: REGISTER ---
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
        
        # --- TAB 3: PASSWORD RESET VIA RESEND ---
        with tab_reset:
            st.subheader("Forgot Password?")
            reset_step = st.radio("Step", ["1. Request PIN", "2. Reset Password"], key="reset_step_radio")
            
            if reset_step == "1. Request PIN":
                reset_email = st.text_input("Account Email", key="reset_email")
                if st.button("Send Reset PIN", use_container_width=True):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM users WHERE email = %s;", (reset_email,))
                    user = cursor.fetchone()
                    
                    if user:
                        pin = ''.join(random.choices(string.digits, k=6))
                        expires_at = datetime.now() + timedelta(minutes=15)
                        
                        # Store PIN in DB
                        cursor.execute(
                            "INSERT INTO password_resets (user_id, token, expires_at) VALUES (%s, %s, %s);",
                            (user["id"], pin, expires_at)
                        )
                        conn.commit()
                        
                        # Send via Resend API
                        try:
                            resend.Emails.send({
                                "from": "Workout AI <onboarding@resend.dev>",
                                "to": [reset_email],
                                "subject": "Password Reset Verification Code",
                                "html": f"<p>Your password reset code is: <strong>{pin}</strong>. It expires in 15 minutes.</p>"
                            })
                            st.success("Verification PIN sent to your email!")
                        except Exception as resend_err:
                            st.error(f"Failed to send email: {resend_err}")
                    else:
                        st.error("No account found with that email.")
                    cursor.close()
                    conn.close()
            
            elif reset_step == "2. Reset Password":
                verify_email = st.text_input("Account Email", key="verify_email")
                pin_input = st.text_input("6-Digit PIN", key="pin_input")
                new_password = st.text_input("New Password", type="password", key="new_password")
                
                if st.button("Confirm Reset", use_container_width=True):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT pr.id, pr.user_id
                        FROM password_resets pr
                        JOIN users u ON u.id = pr.user_id
                        WHERE u.email = %s AND pr.token = %s AND pr.expires_at > NOW()
                        ORDER BY pr.expires_at DESC LIMIT 1;
                    """, (verify_email, pin_input))
                    
                    reset_req = cursor.fetchone()
                    if reset_req:
                        new_hashed = generate_password_hash(new_password)
                        cursor.execute("UPDATE users SET password = %s WHERE id = %s;",
                                       (new_hashed, reset_req["user_id"]))
                        cursor.execute("DELETE FROM password_resets WHERE user_id = %s;", (reset_req["user_id"],))
                        conn.commit()
                        st.success("Password updated! You can now log in.")
                    else:
                        st.error("Invalid or expired PIN.")
                    cursor.close()
                    conn.close()
    
    else:
        st.success("Authorized Session Active")
        if st.button("Logout", use_container_width=True):
            st.session_state["logged_in"] = False
            st.session_state["user_id"] = None
            st.rerun()
        
        # --- DANGER ZONE / ACCOUNT DEACTIVATION ---
        st.divider()
        with st.expander("⚠️ Danger Zone"):
            st.write("Deactivating your account deletes all your workouts and frees up your email.")
            confirm_email = st.text_input("Confirm your email to deactivate:")
            
            if st.button("Delete Account Permanently", type="primary"):
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT email FROM users WHERE id = %s;", (current_user_id,))
                user_data = cursor.fetchone()
                
                if user_data and confirm_email.strip() == user_data["email"]:
                    cursor.execute("DELETE FROM sets WHERE workout_id IN (SELECT id FROM workouts WHERE user_id = %s);",
                                   (current_user_id,))
                    cursor.execute("DELETE FROM workouts WHERE user_id = %s;", (current_user_id,))
                    cursor.execute("DELETE FROM users WHERE id = %s;", (current_user_id,))
                    conn.commit()
                    
                    st.session_state["logged_in"] = False
                    st.session_state["user_id"] = None
                    st.success("Account deleted! Email is now free for new registrations.")
                    st.rerun()
                else:
                    st.error("Email verification failed. Deactivation cancelled.")
                cursor.close()
                conn.close()

# Dashboard View logic
if not is_logged_in:
    st.info("👋 Please log in or register via the sidebar to access your workout portal.")
else:
    current_user_id = st.session_state["user_id"]
    tab_log, tab_history, tab_coach = st.tabs([
        "📝 Log Workout (AI)",
        "📅 Workout History & Management",
        "🧠 AI Personal Coach"
    ])
    
    # --- TAB 1: LOG WORKOUT ---
    with tab_log:
        st.header("Log with Natural Language")
        st.write("Describe your session like a journal entry. AI will map it to database exercises.")
        
        raw_notes = st.text_area(
            "What did you train today?",
            placeholder="e.g., Did 3 sets of Bench Press with 10 reps at 135 lbs, then 3 sets of Squats with 8 reps at 225 lbs.",
            height=120
        )
        
        if st.button("Parse & Save Workout", type="primary"):
            if not raw_notes.strip():
                st.warning("Please type out your workout details first.")
            else:
                with st.spinner("Analyzing log with AI..."):
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT id, name, category FROM exercises;")
                        available_exercises = cursor.fetchall()
                        
                        if not available_exercises:
                            st.error("Could not fetch database exercises.")
                            st.stop()
                        
                        ai = AIService()
                        parsed = ai.parse_workout_text(raw_notes, available_exercises)
                        
                        workout_name = parsed.get("workout_name", "AI Parsed Workout")
                        sets = parsed.get("sets", [])
                        
                        if not sets:
                            st.warning("AI couldn't identify any matching exercises/sets.")
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
    
    # --- TAB 2: HISTORY & EDIT/UNDO/DELETE MANAGEMENT ---
    with tab_history:
        st.subheader("📅 Manage Workout History")
        st.caption(
            "Double-click cells to edit names, check 'Delete?' to remove entries, or click 'Undo' to cancel unsaved edits.")
        
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
                df = pd.DataFrame(workouts)
                df["created_at"] = df["created_at"].astype(str)
                df["Delete"] = False
                
                edited_df = st.data_editor(
                    df,
                    column_config={
                        "id": st.column_config.NumberColumn("Workout ID", disabled=True),
                        "name": st.column_config.TextColumn("Workout Name"),
                        "created_at": st.column_config.TextColumn("Date Logged", disabled=True),
                        "Delete": st.column_config.CheckboxColumn("Delete?"),
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="workout_history_editor"
                )
                
                col_save, col_undo = st.columns([1, 1])
                
                with col_save:
                    if st.button("💾 Save Table Changes", type="primary"):
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        
                        for index, row in edited_df.iterrows():
                            if row["Delete"]:
                                cursor.execute("DELETE FROM sets WHERE workout_id = %s;", (row["id"],))
                                cursor.execute("DELETE FROM workouts WHERE id = %s;", (row["id"],))
                            else:
                                cursor.execute(
                                    "UPDATE workouts SET name = %s WHERE id = %s;",
                                    (row["name"], row["id"])
                                )
                        
                        conn.commit()
                        cursor.close()
                        conn.close()
                        st.success("Changes saved successfully!")
                        st.rerun()
                
                with col_undo:
                    if st.button("↩️ Discard / Undo Unsaved Edits"):
                        st.rerun()
            else:
                st.info("No workouts logged yet!")
        except Exception as e:
            st.error(f"Error loading history: {e}")
    
    # --- TAB 3: COACHING ADVICE ---
    with tab_coach:
        st.header("🧠 AI Personal Coach Insights")
        st.write("Let the AI evaluate your progression targets and provide progressive overload goals.")
        
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