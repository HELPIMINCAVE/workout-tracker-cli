import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CONFIG_DIR = Path.home() / ".workout_cli"
TOKEN_FILE = CONFIG_DIR / "auth.json"

BASE_URL = os.getenv("API_BASE_URL", default="http://127.0.0.1:8000")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", default="")

def save_token(token_string: str) -> None:
    CONFIG_DIR.mkdir(exist_ok=True, parents=True)
    
    with open(TOKEN_FILE, "w") as f:
        json.dump({"token": token_string}, f)

def load_token() -> str | None:
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
            return data.get("token")
    
    return None

def clear_token() -> None:
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()