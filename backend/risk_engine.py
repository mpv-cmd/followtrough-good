from datetime import date
from collections import defaultdict


def detect_task_risks(actions):

    today = str(date.today())

    risks = []

    deadline_map = defaultdict(list)

    for a in actions:

        d = a.get("deadline")

        if not d:
            continue

        deadline_map[d].append(a)

    for d, tasks in deadline_map.items():

        if len(tasks) >= 3:

            risks.append({
                "type": "overload",
                "deadline": d,
                "count": len(tasks),
                "message": f"{len(tasks)} tasks scheduled for {d}"
            })

    for a in actions:

        if not a.get("deadline"):

            risks.append({
                "type": "missing_deadline",
                "task": a["action"],
                "message": "Task has no deadline"
            })

    return risks