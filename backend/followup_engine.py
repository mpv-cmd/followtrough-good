from datetime import date
from followup_ai import generate_followup


def detect_and_generate_followups(actions):

    today = str(date.today())

    followups = []

    for a in actions:

        deadline = a.get("deadline")

        if not deadline:
            continue

        if deadline < today:

            message = generate_followup(a)

            followups.append({
                "task": a.get("action"),
                "deadline": deadline,
                "message": message
            })

    return followups