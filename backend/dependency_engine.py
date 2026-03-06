import re

DEPENDENCY_WORDS = [
    "after",
    "before",
    "once",
    "depends",
    "waiting for",
    "blocked by"
]


def detect_dependencies(actions):

    dependencies = []

    for a in actions:

        text = (a.get("action") or "").lower()

        for w in DEPENDENCY_WORDS:
            if w in text:

                dependencies.append({
                    "task": a.get("action"),
                    "dependency_word": w
                })

    return dependencies