import os
from openai import OpenAI
from company_brain import build_company_brain

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def ask_meeting_copilot(question, meetings):

    brain = build_workspace_brain(workspace)

    prompt = f"""
You are an AI COO helping manage a company.

Here is the current company brain:

{brain}

Answer this question about the company:

{question}

Be concise and actionable.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful AI operations assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    return response.choices[0].message.content