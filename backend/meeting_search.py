from openai import OpenAI

client = OpenAI()


def search_meetings(question, meetings):

    context = ""

    for m in meetings[-10:]:
        context += f"\nMeeting summary:\n{m.get('summary','')}\n"
        context += f"Tasks:\n"

        for a in m.get("actions", []):
            context += f"- {a.get('action')} (deadline: {a.get('deadline')})\n"

    prompt = f"""
You are an assistant helping search past meetings.

Answer the question using the meeting data.

Question:
{question}

Meetings:
{context}

Answer clearly and concisely.
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}]
    )

    return res.choices[0].message.content