from openai import OpenAI

client = OpenAI()

def detect_decisions(transcript: str):

    prompt = f"""
Analyze this meeting transcript and extract decisions made.

Transcript:
{transcript}

Return a bullet list of decisions only.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"user","content":prompt}
        ]
    )

    return response.choices[0].message.content