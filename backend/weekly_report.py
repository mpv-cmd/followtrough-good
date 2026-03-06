from openai import OpenAI

client = OpenAI()


def generate_weekly_report(meetings):

    context = ""

    for m in meetings:

        summary = m.get("summary", "")
        actions = m.get("actions", [])

        context += f"\nMEETING SUMMARY:\n{summary}\n"

        if actions:
            context += "ACTIONS:\n"
            for a in actions:
                context += f"- {a.get('action')} (deadline: {a.get('deadline')})\n"

    prompt = f"""
You are an AI assistant generating a weekly team progress report.

Based on the meeting history below, produce a report with:

Completed
Pending
Overdue

Meeting history:
{context}
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    return res.choices[0].message.content