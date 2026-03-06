from openai import OpenAI

client = OpenAI()

def extract_knowledge(transcript: str):

    prompt = f"""
Extract structured knowledge from this meeting.

Return entities and relationships.

Example format:

Entity: Stripe
Type: Payment Provider

Entity: Landing Page
Owner: Alex
Deadline: 2026-05-10

Transcript:
{transcript}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"user","content":prompt}
        ]
    )

    return response.choices[0].message.content