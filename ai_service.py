import json
import os
from google import genai
from google.genai import types

class AIService:
    def __init__(self):
        self.client = genai.Client()
        self.model = "gemini-2.0-flash"
    
    def parse_workout_text(self, raw_notes: str, available_exercises: list) -> dict:
        prompt = f"""
        You are a workout parser assistant.
        Analyze the user's workout log and map matched movements to the provided reference exercise IDs.

        Reference Exercise Database:
        {json.dumps(available_exercises)}

        User Log:
        "{raw_notes}"

        Return JSON in this format:
        {{
            "workout_name": "Short summary name (e.g., Push Day)",
            "sets": [
                {{
                    "exercise_id": <int matching reference ID>,
                    "reps": <int>,
                    "weight": <float>,
                    "set_order": <int starting at 1>
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

    def get_coaching_advice(self, history_data: list) -> str:
        prompt = f"""
        You are an expert AI strength and fitness coach.
        Review this user's workout history and offer actionable feedback and progressive overload targets for their next session.

        Workout History:
        {json.dumps(history_data, default=str)}
        """

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt
        )

        return response.text