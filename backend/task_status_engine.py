from datetime import datetime


def detect_task_status(actions):

    results = []

    today = datetime.today().date()

    for a in actions:

        deadline = a.get("deadline")
        title = a.get("action", "")

        status = "in_progress"

        if not deadline:
            status = "unknown"

        else:
            try:
                due = datetime.fromisoformat(deadline).date()

                if due < today:
                    status = "overdue"

                elif (due - today).days <= 2:
                    status = "at_risk"

                else:
                    status = "in_progress"

            except:
                status = "unknown"

        results.append({
            "task": title,
            "deadline": deadline,
            "status": status
        })

    return results