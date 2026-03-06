def generate_dashboard(meetings, actions):

    summaries = "\n\n".join([
        str(m.get("summary", "")) for m in meetings
    ])

    dashboard = {
        "total_meetings": len(meetings),
        "total_actions": len(actions),
        "latest_summary": summaries[-500:]
    }

    return dashboard