def simulate_project(actions, dependencies):

    simulations = []

    for dep in dependencies:

        task = dep.get("task")

        simulations.append({
            "scenario": f"If '{task}' is delayed",
            "impact": "Dependent tasks may shift schedule",
            "risk_level": "medium"
        })

    return simulations