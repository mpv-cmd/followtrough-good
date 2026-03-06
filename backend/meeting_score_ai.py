from openai import OpenAI

client = OpenAI()

def generate_meeting_score(transcript: str):

    prompt = f"""
Evaluate the effectiveness of this meeting.

Transcript:
{transcript}

Return:

Score (1-10)

Strengths
Issues
Recommendations
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"user","content":prompt}
        ]
    )

    return response.choices[0].message.content