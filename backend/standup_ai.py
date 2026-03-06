from openai import OpenAI

client = OpenAI()

def generate_standup(actions):

    context = ""

    for a in actions:
        task = a.get("action")
        deadline = a.get("deadline")
        context += f"- {task} (deadline: {deadline})\n"

    prompt = f"""
Generate a daily standup summary for a team.

Tasks:
{context}

Return a short structured summary including:
- completed
- in progress
- blocked
- today focus
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content