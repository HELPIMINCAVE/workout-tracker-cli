import json
import os
from groq import Groq

class AIService:
    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"

    def parse_workout_text(self, raw_notes: str, available_exercises: list) -> dict:
        prompt = f"""
        You are a workout parser assistant.
        Analyze the user's workout log and map matched movements to the reference exercise IDs.

        Database Exercises:
        {json.dumps(available_exercises)}

        User Log:
        "{raw_notes}"

        Return JSON in this exact format:
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

        response = self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a helpful workout parsing assistant that outputs strictly JSON."},
                {"role": "user", "content": prompt}
            ]
        )

        return json.loads(response.choices[0].message.content)

    def get_coaching_advice(self, history_data: list) -> str:
        prompt = f"""
        You are an expert AI strength and fitness coach.
        Review this user's workout history and offer actionable feedback and progressive overload targets for their next session.

        Workout History:
        {json.dumps(history_data, default=str)}
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert strength coach giving concise, actionable advice."},
                {"role": "user", "content": prompt}
            ]
        )

        return response.choices[0].message.content