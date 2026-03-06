from datetime import datetime


def build_meeting_timeline(meetings):

    timeline = []

    for m in meetings:

        summary = m.get("summary", "")
        actions = m.get("actions", [])
        date = m.get("created_at", None)

        timeline.append({
            "date": date,
            "summary": summary,
            "tasks": len(actions),
            "key_actions": [a.get("action") for a in actions[:3]]
        })

    timeline.sort(key=lambda x: x["date"] or "")

    return timeline