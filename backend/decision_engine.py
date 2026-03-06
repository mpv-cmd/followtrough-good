import re

DECISION_WORDS = [
    "decided",
    "decision",
    "agreed",
    "we will",
    "approved",
    "finalized"
]


def extract_decisions(transcript):

    decisions = []

    sentences = re.split(r"(?<=[.!?])\s+", transcript or "")

    for s in sentences:

        text = s.lower()

        if any(w in text for w in DECISION_WORDS):

            decisions.append({
                "decision": s.strip(),
                "confidence": 0.8
            })

    return decisions[:10]
