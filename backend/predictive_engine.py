def predict_project_risks(meetings, actions):

    summaries = "\n\n".join([
        str(m.get("summary", "")) for m in meetings
    ])

    risks = []

    if "delay" in summaries.lower():
        risks.append("Project delay risk detected")

    if "blocked" in summaries.lower():
        risks.append("Blockers may slow progress")

    if len(actions) > 20:
        risks.append("Too many tasks may overload the team")

    if not risks:
        risks.append("Project risk appears low")

    return risks