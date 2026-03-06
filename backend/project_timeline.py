from openai import OpenAI

client = OpenAI()

def generate_project_timeline(meetings):

    context = "\n\n".join([
        m.get("summary", "") for m in meetings
    ])

    prompt = f"""
Analyze these meeting summaries and reconstruct a project timeline.

Meetings:
{context}

Generate a timeline of project progress.
Use sections like Week 1, Week 2 etc.

Be concise.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"user","content":prompt}
        ]
    )

    return response.choices[0].message.content