from datetime import datetime


def detect_followups(previous_meetings, new_actions):

    followups = []

    now = datetime.utcnow().date()

    for meeting in previous_meetings:

        for action in meeting.get("actions", []):

            deadline = action.get("deadline")

            if not deadline:
                continue

            try:
                d = datetime.fromisoformat(deadline).date()
            except:
                continue

            if d < now:
                followups.append({
                    "action": action.get("action"),
                    "deadline": deadline,
                    "status": "overdue"
                })

    return followups