import uuid
from transcribe import transcribe_file
from summarize_meeting import summarize_meeting
from extract_action import extract_actions

async def process_meeting(file):

    transcript = transcribe_file(file)
    summary = summarize_meeting(transcript)
    actions = extract_actions(transcript)

    return {
        "transcript": transcript,
        "summary": summary,
        "actions": actions
    }