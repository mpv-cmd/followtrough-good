def estimate_duration_minutes(action_text: str) -> int:
    """
    Very simple heuristic for estimating task duration.
    """

    text = action_text.lower()

    if "email" in text:
        return 10

    if "call" in text or "meeting" in text:
        return 30

    if "review" in text or "read" in text:
        return 20

    if "write" in text or "draft" in text:
        return 40

    if "prepare" in text:
        return 45

    if "fix" in text or "debug" in text:
        return 60

    # default
    return 30