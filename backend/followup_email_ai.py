from openai import OpenAI

client = OpenAI()

def generate_followup_email(summary, actions, decisions):

    actions_text = "\n".join([
        f"- {a.get('action','')}"
        for a in actions
    ])

    prompt = f"""
Write a professional meeting follow-up email.

Meeting summary:
{summary}

Decisions:
{decisions}

Action items:
{actions_text}

Keep it short and professional.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content