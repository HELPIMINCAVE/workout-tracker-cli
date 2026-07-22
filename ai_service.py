import json
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from config import GEMINI_API_KEY

load_dotenv()

class AIService:
    def __init__(self):
        key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
        
        if not key:
            raise ValueError(
                "GEMINI_API_KEY is missing! Set it in your .env file or environment."
            )
        
        self.api_key: str = key
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-3.5-flash"

    def parse_workout_text(self, raw_input: str, exercise_list: list) -> dict:
        exercises_str = "\n".join(
            [f"ID {ex['id']}: {ex['name']} (Category: {ex.get('category', 'General')})" for ex in exercise_list]
        )

        prompt = f"""
        You are a workout tracking parser. Match the user's logged input to the correct exercise IDs.

        Available Exercises in Database:
        {exercises_str}

        User Input: "{raw_input}"

        Requirements:
        1. Map each exercise performed in the input to its exact `exercise_id` from the list above.
        2. Infer realistic workout names like "Chest & Triceps", "Leg Day", "Full Body", etc.
        3. Parse reps, weights (in numeric values), and assign 1-based sequential `set_order` numbers.

        Output ONLY valid JSON matching this schema:
        {{
            "workout_name": "Summary Workout Title",
            "sets": [
                {{
                    "exercise_id": <int>,
                    "reps": <int>,
                    "weight": <float>,
                    "set_order": <int>
                }}
            ]
        }}
        """

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)

    def get_coaching_advice(self, workout_history: list) -> str:
        prompt = f"""
        You are an expert personal trainer. Review the following recent workout history:
        {json.dumps(workout_history, indent=2)}
        Provide 2-3 concise, encouraging recommendations for progression (e.g., weight adjustments, volume changes, recovery advice).
        Keep the formatting clean for a CLI terminal view.
        """

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text