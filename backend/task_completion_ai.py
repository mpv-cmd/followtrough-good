from openai import OpenAI

client = OpenAI()

def detect_completed_tasks(transcript, actions):

    actions_text = "\n".join([
        a.get("action","") for a in actions
    ])

    prompt = f"""
We have these tasks:

{actions_text}

Analyze this meeting transcript and detect if any tasks were completed.

Transcript:
{transcript}

Return the completed tasks only.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"user","content":prompt}
        ]
    )

    return response.choices[0].message.content