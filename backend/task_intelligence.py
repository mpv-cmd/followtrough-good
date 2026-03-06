# backend/task_intelligence.py

from __future__ import annotations

import re
from typing import Dict


# ---------------------------------------
# KEYWORD INTELLIGENCE
# ---------------------------------------

HIGH_PRIORITY_WORDS = [
    "urgent",
    "asap",
    "immediately",
    "today",
    "critical",
    "priority",
]

MEDIUM_PRIORITY_WORDS = [
    "soon",
    "this week",
    "follow up",
    "review",
]

LONG_TASK_WORDS = [
    "build",
    "create",
    "prepare",
    "write",
    "design",
    "develop",
    "analyze",
    "implement",
]

SHORT_TASK_WORDS = [
    "send",
    "email",
    "call",
    "reply",
    "schedule",
    "confirm",
    "book",
]


# ---------------------------------------
# DURATION ESTIMATION
# ---------------------------------------

def estimate_duration(action: str) -> int:
    """
    Estimate task duration in minutes
    """

    text = action.lower()

    if any(word in text for word in LONG_TASK_WORDS):
        return 60

    if any(word in text for word in SHORT_TASK_WORDS):
        return 15

    return 30


# ---------------------------------------
# PRIORITY ESTIMATION
# ---------------------------------------

def estimate_priority(action: str) -> str:
    """
    Returns:
        high
        medium
        low
    """

    text = action.lower()

    if any(word in text for word in HIGH_PRIORITY_WORDS):
        return "high"

    if any(word in text for word in MEDIUM_PRIORITY_WORDS):
        return "medium"

    return "low"


# ---------------------------------------
# SMART TIME SCHEDULING
# ---------------------------------------

def estimate_best_time(priority: str) -> str:
    """
    Decide the best hour to schedule the task
    """

    if priority == "high":
        return "09:00"

    if priority == "medium":
        return "11:00"

    return "14:00"


# ---------------------------------------
# MAIN ENRICHMENT FUNCTION
# ---------------------------------------

def enrich_task(action: str) -> Dict:
    """
    Adds AI intelligence to tasks

    Returns:
    {
        priority: high|medium|low
        duration: minutes
        start_time: HH:MM
    }
    """

    priority = estimate_priority(action)
    duration = estimate_duration(action)
    start_time = estimate_best_time(priority)

    return {
        "priority": priority,
        "duration": duration,
        "start_time": start_time,
    }