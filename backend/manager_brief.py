from datetime import date
from collections import defaultdict


def generate_manager_brief(actions):

    today = date.today()

    overdue = []
    missing_deadlines = []
    workload = defaultdict(list)

    for a in actions:

        task = a.get("action")
        deadline = a.get("deadline")

        if not deadline:
            missing_deadlines.append(task)
            continue

        workload[deadline].append(task)

        if deadline < str(today):
            overdue.append(task)

    workload_risk = []

    for d, tasks in workload.items():

        if len(tasks) >= 3:
            workload_risk.append(f"{d} has {len(tasks)} tasks")

    recommendations = []

    if overdue:
        recommendations.append("Follow up on overdue tasks")

    if missing_deadlines:
        recommendations.append("Assign deadlines to all tasks")

    if workload_risk:
        recommendations.append("Redistribute workload to avoid deadline congestion")

    summary = "Team risk detected" if overdue or workload_risk else "Team operating normally"

    return {
        "summary": summary,
        "overdue": overdue,
        "missing_deadlines": missing_deadlines,
        "workload_risk": workload_risk,
        "recommendations": recommendations
    }