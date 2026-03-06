from openai import OpenAI

client = OpenAI()


def detect_completed_tasks(transcript: str, actions: list):

    prompt = f"""
From this meeting transcript identify if any tasks are mentioned as completed.

Transcript:
{transcript}

Tasks:
{actions}

Return a list of completed tasks only.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.choices[0].message.content

    completed = [x.strip("- ").strip() for x in text.split("\n") if x.strip()]

    return completed