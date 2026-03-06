from openai import OpenAI

client = OpenAI()

def generate_manager_brief(meetings):

    summaries = "\n\n".join([
        m.get("summary","") for m in meetings
    ])

    prompt = f"""
You are an executive assistant.

Analyze these meeting summaries and generate a manager brief.

Meetings:
{summaries}

Return:

Progress
Risks
Decisions
Next Steps
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"user","content":prompt}
        ]
    )

    return response.choices[0].message.content