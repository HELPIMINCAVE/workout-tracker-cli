import httpx
from config import BASE_URL, load_token, save_token


class APIClient:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
    
    def _get_headers(self) -> dict:
        token = load_token()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers
    
    def register(self, email, password) -> dict | None:
        url = f"{self.base_url}/auth/register"
        payload = {"email": email, "password": password}
        
        response = httpx.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    
    def login(self, email: str, password: str) -> bool:
        response = httpx.post(
            f"{self.base_url}/auth/login",
            data={"username": email, "password": password}
        )
        if response.status_code == 200:
            token_payload = response.json()
            token = token_payload.get("access_token")
            save_token(token)
            return True
        return False
    
    def get_exercises(self) -> list:
        url = f"{self.base_url}/exercises"
        response = httpx.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def get_workouts(self) -> list:
        url = f"{self.base_url}/workouts"
        response = httpx.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def create_workout(self, name) -> dict:
        url = f"{self.base_url}/workouts"
        payload = {"name": name}
        
        response = httpx.post(url, json=payload, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def add_set(self, workout_id: int, exercise_id: int, reps: int, weight: float, set_order: int) -> dict:
        url = f"{self.base_url}/workouts/{workout_id}/sets"
        payload = {
            "exercise_id": exercise_id,
            "reps": reps,
            "weight": weight,
            "set_order": set_order
        }
        
        response = httpx.post(url, json=payload, headers=self._get_headers())
        response.raise_for_status()
        return response.json()