def generate_insights(meetings, actions):

    summaries = "\n\n".join([
        str(m.get("summary", "")) for m in meetings
    ])

    insights = []

    if len(actions) > 10:
        insights.append("Large number of action items created")

    if "delay" in summaries.lower():
        insights.append("Possible project delays mentioned")

    if "blocked" in summaries.lower():
        insights.append("Team members reported blockers")

    if not insights:
        insights.append("No major risks detected")

    return insights