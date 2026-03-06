from openai import OpenAI
from datetime import date

client = OpenAI()


def generate_followup(task):

    action = task.get("action")
    deadline = task.get("deadline")

    prompt = f"""
Write a short professional follow-up message.

Task: {action}
Deadline: {deadline}

Keep it concise and friendly.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content