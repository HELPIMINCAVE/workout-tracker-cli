import streamlit as st
import pandas as pd
from ai_service import AIService
import time, os, re, secrets, psycopg2, resend, dns.resolver
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash

st.set_page_config(
    page_title="Workout Tracker AI",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded"
)

query_params = st.query_params
if "ping" in query_params:
    st.write("OK")
    st.stop()

APP_URL = "https://workout-tracker-cli.onrender.com".rstrip("/")
resend.api_key = os.environ.get("RESEND_API_KEY")


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


def generate_otp() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def is_valid_email_format(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(pattern, email.strip()) is not None


def domain_has_mx_records(email: str) -> bool:
    try:
        domain = email.split('@')[1]
        records = dns.resolver.resolve(domain, 'MX')
        return len(records) > 0
    except Exception:
        return False


def validate_password_strength(password: str):
    if len(password) < 10:
        return False, "Password must be at least 10 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least 1 uppercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least 1 number."
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?~`]", password):
        return False, "Password must contain at least 1 symbol."
    
    lower_pass = password.lower()
    for i in range(len(lower_pass) - 3):
        chunk = lower_pass[i:i + 4]
        if all(ord(chunk[j + 1]) - ord(chunk[j]) == 1 for j in range(3)):
            return False, f"Password cannot contain sequential patterns like '{chunk}'."
        if all(ord(chunk[j]) - ord(chunk[j + 1]) == 1 for j in range(3)):
            return False, f"Password cannot contain sequential patterns like '{chunk}'."
    
    return True, ""


if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_id" not in st.session_state:
    st.session_state["user_id"] = None
if "otp_step" not in st.session_state:
    st.session_state["otp_step"] = None
if "otp_user_id" not in st.session_state:
    st.session_state["otp_user_id"] = None
if "otp_email" not in st.session_state:
    st.session_state["otp_email"] = None

is_logged_in = st.session_state["logged_in"]

with st.sidebar:
    st.title("🏋️ Workout Tracker AI")
    st.write("Log workouts naturally & get smart coaching.")
    st.divider()
    
    if not is_logged_in:
        
        if st.session_state["otp_step"] is not None:
            st.subheader("🔑 Enter 6-Digit OTP")
            st.caption(f"Code sent to **{st.session_state['otp_email']}** (Valid for 10 min)")
            
            entered_otp = st.text_input("6-Digit Code", max_chars=6, key="input_otp")
            
            if st.session_state["otp_step"] == "verify_reg":
                if st.button("Verify Account", type="primary", use_container_width=True):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id FROM password_resets
                        WHERE user_id = %s AND token = %s AND expires_at > NOW()
                        ORDER BY expires_at DESC LIMIT 1;
                    """, (st.session_state["otp_user_id"], entered_otp.strip()))
                    valid_token = cursor.fetchone()
                    
                    if valid_token:
                        cursor.execute("UPDATE users SET is_verified = TRUE WHERE id = %s;",
                                       (st.session_state["otp_user_id"],))
                        cursor.execute("DELETE FROM password_resets WHERE user_id = %s;",
                                       (st.session_state["otp_user_id"],))
                        conn.commit()
                        st.success("🎉 Email verified successfully! You can now log in.")
                        st.session_state["otp_step"] = None
                        st.rerun()
                    else:
                        st.error("Invalid or expired OTP.")
                    cursor.close()
                    conn.close()
            
            elif st.session_state["otp_step"] == "login_2fa":
                if st.button("Verify & Login", type="primary", use_container_width=True):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id FROM password_resets
                        WHERE user_id = %s AND token = %s AND expires_at > NOW()
                        ORDER BY expires_at DESC LIMIT 1;
                    """, (st.session_state["otp_user_id"], entered_otp.strip()))
                    valid_token = cursor.fetchone()
                    
                    if valid_token:
                        cursor.execute("DELETE FROM password_resets WHERE user_id = %s;",
                                       (st.session_state["otp_user_id"],))
                        conn.commit()
                        st.session_state["logged_in"] = True
                        st.session_state["user_id"] = st.session_state["otp_user_id"]
                        st.session_state["otp_step"] = None
                        st.success("Authenticated!")
                        st.rerun()
                    else:
                        st.error("Invalid or expired OTP.")
                    cursor.close()
                    conn.close()
            
            elif st.session_state["otp_step"] == "reset_pass":
                new_reset_pass = st.text_input("New Password", type="password", key="otp_new_pass")
                if st.button("Update Password", type="primary", use_container_width=True):
                    is_pass_valid, pass_err_msg = validate_password_strength(new_reset_pass)
                    if not is_pass_valid:
                        st.error(pass_err_msg)
                    else:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT id FROM password_resets
                            WHERE user_id = %s AND token = %s AND expires_at > NOW()
                            ORDER BY expires_at DESC LIMIT 1;
                        """, (st.session_state["otp_user_id"], entered_otp.strip()))
                        valid_token = cursor.fetchone()
                        
                        if valid_token:
                            hashed_pass = generate_password_hash(new_reset_pass)
                            cursor.execute("UPDATE users SET password = %s WHERE id = %s;",
                                           (hashed_pass, st.session_state["otp_user_id"]))
                            cursor.execute("DELETE FROM password_resets WHERE user_id = %s;",
                                           (st.session_state["otp_user_id"],))
                            conn.commit()
                            st.success("🎉 Password reset successfully! Please log in.")
                            st.session_state["otp_step"] = None
                            st.rerun()
                        else:
                            st.error("Invalid or expired OTP.")
                        cursor.close()
                        conn.close()
            
            if st.button("Cancel / Back", use_container_width=True):
                st.session_state["otp_step"] = None
                st.rerun()
        
        else:
            tab_login, tab_register, tab_reset = st.tabs(["Login", "Register", "Reset Password"])
            
            with tab_login:
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_pass")
                
                if st.button("Login", use_container_width=True):
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT id, password, is_verified FROM users WHERE email = %s;",
                                       (email.strip().lower(),))
                        user = cursor.fetchone()
                        
                        if user and check_password_hash(user["password"], password):
                            clean_email = email.strip().lower()
                            user_id = user["id"]
                            
                            if not user.get("is_verified", True):
                                st.warning("Account unverified. Sending verification OTP...")
                                st.session_state["otp_step"] = "verify_reg"
                            else:
                                st.session_state["otp_step"] = "login_2fa"
                            
                            otp_code = generate_otp()
                            expires_at = datetime.now() + timedelta(minutes=10)
                            
                            cursor.execute("DELETE FROM password_resets WHERE user_id = %s;", (user_id,))
                            cursor.execute(
                                "INSERT INTO password_resets (user_id, token, expires_at) VALUES (%s, %s, %s);",
                                (user_id, otp_code, expires_at)
                            )
                            conn.commit()
                            
                            resend.Emails.send({
                                "from": "Workout AI <onboarding@resend.dev>",
                                "to": [clean_email],
                                "subject": f"Your Verification Code: {otp_code}",
                                "html": f"""
                                <h2>Workout Tracker AI</h2>
                                <p>Your 6-digit OTP verification code is:</p>
                                <h1 style="font-size: 32px; letter-spacing: 5px; color: #007bff;">{otp_code}</h1>
                                <p>This code expires in 10 minutes.</p>
                                """
                            })
                            
                            st.session_state["otp_user_id"] = user_id
                            st.session_state["otp_email"] = clean_email
                            cursor.close()
                            conn.close()
                            st.rerun()
                        else:
                            st.error("Invalid credentials.")
                            cursor.close()
                            conn.close()
                    except Exception as e:
                        st.error(f"Login error: {e}")
            
            with tab_register:
                reg_email = st.text_input("Email", key="reg_email")
                reg_password = st.text_input("Password", type="password", key="reg_pass")
                
                st.caption("Password requirements: 10+ chars, 1 uppercase, 1 number, 1 symbol, no sequential patterns.")
                
                if st.button("Register Account", use_container_width=True):
                    clean_email = reg_email.strip().lower()
                    is_pass_valid, pass_err_msg = validate_password_strength(reg_password)
                    
                    if not clean_email or not reg_password:
                        st.warning("Please fill out both fields.")
                    elif not is_valid_email_format(clean_email):
                        st.error("Please enter a valid email address.")
                    elif not domain_has_mx_records(clean_email):
                        st.error("This email domain doesn't exist.")
                    elif not is_pass_valid:
                        st.error(f"Weak Password: {pass_err_msg}")
                    else:
                        try:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            hashed_password = generate_password_hash(reg_password)
                            
                            cursor.execute(
                                "INSERT INTO users (email, password, is_verified) VALUES (%s, %s, FALSE) RETURNING id;",
                                (clean_email, hashed_password)
                            )
                            new_user_id = cursor.fetchone()["id"]
                            
                            otp_code = generate_otp()
                            expires_at = datetime.now() + timedelta(minutes=10)
                            
                            cursor.execute(
                                "INSERT INTO password_resets (user_id, token, expires_at) VALUES (%s, %s, %s);",
                                (new_user_id, otp_code, expires_at)
                            )
                            conn.commit()
                            
                            resend.Emails.send({
                                "from": "Workout AI <onboarding@resend.dev>",
                                "to": [clean_email],
                                "subject": f"Verify Account OTP: {otp_code}",
                                "html": f"""
                                <h2>Welcome to Workout Tracker AI!</h2>
                                <p>Your 6-digit registration OTP code is:</p>
                                <h1 style="font-size: 32px; letter-spacing: 5px; color: #007bff;">{otp_code}</h1>
                                <p>Enter this code in the application to complete your activation.</p>
                                """
                            })
                            
                            st.session_state["otp_step"] = "verify_reg"
                            st.session_state["otp_user_id"] = new_user_id
                            st.session_state["otp_email"] = clean_email
                            
                            cursor.close()
                            conn.close()
                            st.rerun()
                        except psycopg2.errors.UniqueViolation:
                            st.error("An account with this email already exists.")
                        except Exception as e:
                            st.error(f"Registration failed: {e}")
            
            with tab_reset:
                st.subheader("Forgot Password?")
                reset_email = st.text_input("Account Email", key="reset_email")
                if st.button("Send Reset OTP", use_container_width=True):
                    clean_email = reset_email.strip().lower()
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM users WHERE email = %s;", (clean_email,))
                    user = cursor.fetchone()
                    
                    if user:
                        otp_code = generate_otp()
                        expires_at = datetime.now() + timedelta(minutes=10)
                        
                        cursor.execute("DELETE FROM password_resets WHERE user_id = %s;", (user["id"],))
                        cursor.execute(
                            "INSERT INTO password_resets (user_id, token, expires_at) VALUES (%s, %s, %s);",
                            (user["id"], otp_code, expires_at)
                        )
                        conn.commit()
                        
                        resend.Emails.send({
                            "from": "Workout AI <onboarding@resend.dev>",
                            "to": [clean_email],
                            "subject": f"Password Reset Code: {otp_code}",
                            "html": f"""
                            <h3>Password Reset Request</h3>
                            <p>Use the following 6-digit OTP code to reset your password:</p>
                            <h1 style="font-size: 32px; letter-spacing: 5px; color: #dc3545;">{otp_code}</h1>
                            """
                        })
                        
                        st.session_state["otp_step"] = "reset_pass"
                        st.session_state["otp_user_id"] = user["id"]
                        st.session_state["otp_email"] = clean_email
                        cursor.close()
                        conn.close()
                        st.rerun()
                    else:
                        st.error("No account found with that email.")
                    cursor.close()
                    conn.close()
    
    else:
        st.success("Authorized Session Active")
        if st.button("Logout", use_container_width=True):
            st.session_state["logged_in"] = False
            st.session_state["user_id"] = None
            st.rerun()
        
        st.divider()
        with st.expander("⚠️ Danger Zone"):
            st.write("Deactivating your account deletes all your workouts and frees up your email.")
            confirm_email = st.text_input("Confirm your email to deactivate:")
            
            if st.button("Delete Account Permanently", type="primary"):
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT email FROM users WHERE id = %s;", (st.session_state["user_id"],))
                user_data = cursor.fetchone()
                
                if user_data and confirm_email.strip().lower() == user_data["email"]:
                    cursor.execute("DELETE FROM sets WHERE workout_id IN (SELECT id FROM workouts WHERE user_id = %s);",
                                   (st.session_state["user_id"],))
                    cursor.execute("DELETE FROM workouts WHERE user_id = %s;", (st.session_state["user_id"],))
                    cursor.execute("DELETE FROM users WHERE id = %s;", (st.session_state["user_id"],))
                    conn.commit()
                    
                    st.session_state["logged_in"] = False
                    st.session_state["user_id"] = None
                    st.success("Account deleted!")
                    st.rerun()
                else:
                    st.error("Email verification failed. Deactivation cancelled.")
                cursor.close()
                conn.close()

if not is_logged_in:
    st.info("👋 Please log in or register via the sidebar to access your workout portal.")
else:
    current_user_id = st.session_state["user_id"]
    tab_log, tab_history, tab_coach = st.tabs([
        "📝 Log Workout (AI)",
        "📅 Workout History & Management",
        "🧠 AI Personal Coach"
    ])
    
    with tab_log:
        st.header("Log with Natural Language")
        st.write("Describe your session like a journal entry. AI will map it to database exercises.")
        
        raw_notes = st.text_area(
            "What did you train today?",
            placeholder="e.g., Did 3 sets of Bench Press with 10 reps at 135 lbs, then 3 sets of Push-ups with 20 reps.",
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
                                weight_val = s.get("weight") if s.get("weight") is not None else 0.0
                                reps_val = s.get("reps") if s.get("reps") is not None else 1
                                set_order_val = s.get("set_order") if s.get("set_order") is not None else 1
                                
                                cursor.execute(
                                    """INSERT INTO sets (workout_id, exercise_id, reps, weight, set_order)
                                       VALUES (%s, %s, %s, %s, %s);""",
                                    (workout_id, s["exercise_id"], reps_val, weight_val, set_order_val)
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
        st.subheader("📅 Manage Workout History")
        st.caption("Edit workout names inline or click 'Delete' to permanently remove an entire session.")
        
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
                for w in workouts:
                    with st.container():
                        col_id, col_name, col_date, col_actions = st.columns([1, 4, 3, 2])
                        
                        with col_id:
                            st.write(f"**#{w['id']}**")
                        
                        with col_name:
                            new_name = st.text_input("Name", value=w["name"], key=f"name_{w['id']}",
                                                     label_visibility="collapsed")
                        
                        with col_date:
                            st.write(str(w["created_at"])[:16])
                        
                        with col_actions:
                            col_save_btn, col_del_btn = st.columns([1, 1])
                            
                            with col_save_btn:
                                if st.button("💾", key=f"save_{w['id']}", help="Save Name Edit"):
                                    conn = get_db_connection()
                                    cursor = conn.cursor()
                                    cursor.execute("UPDATE workouts SET name = %s WHERE id = %s;", (new_name, w["id"]))
                                    conn.commit()
                                    cursor.close()
                                    conn.close()
                                    st.toast("Workout updated!")
                                    st.rerun()
                            
                            with col_del_btn:
                                if st.button("🗑️ Delete", key=f"del_{w['id']}", type="secondary",
                                             help="Delete entire workout day"):
                                    conn = get_db_connection()
                                    cursor = conn.cursor()
                                    cursor.execute("DELETE FROM sets WHERE workout_id = %s;", (w["id"],))
                                    cursor.execute("DELETE FROM workouts WHERE id = %s;", (w["id"],))
                                    conn.commit()
                                    cursor.close()
                                    conn.close()
                                    st.toast(f"Deleted workout #{w['id']}")
                                    st.rerun()
                        st.divider()
            else:
                st.info("No workouts logged yet!")
        except Exception as e:
            st.error(f"Error loading history: {e}")
    
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