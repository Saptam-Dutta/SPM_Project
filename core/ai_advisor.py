"""
ai_advisor.py
-------------
The AI half of the app. Given the conflicts the deterministic scheduler
found (scheduler.py), asks Gemini which tasks to delay - and by how many
days - to smooth out the resource overallocation, while respecting each
task's own deadline/slack wherever possible.

This is deliberately kept separate from scheduler.py: the scheduler decides
FACTS (is there a conflict, how much slack exists), the AI advisor makes a
JUDGMENT CALL (which tasks to move) that a person then reviews and can
accept, edit, or ignore.
"""

import json

import pandas as pd

from .llm_client import call_llm, parse_json_reply


PROMPT_INSTRUCTIONS = """
You are a project scheduling assistant. You will be given:
  - a list of tasks, each with its start date, duration, deadline, and
    slack (days it can slip without missing its own deadline)
  - a list of resources and their daily capacity
  - a summary of resource conflicts (days where demand exceeds capacity)

Your job is RESOURCE SMOOTHING: recommend delaying specific tasks, by a
specific number of days each, to reduce or eliminate the resource conflicts
- WITHOUT exceeding any task's available slack (so no deadline is missed).
Prefer delaying tasks that have the most slack and the least schedule
impact. Only recommend delaying a task if it is actually contributing to a
conflict.

If the conflicts cannot be fully resolved using the available slack alone,
say so plainly - that is a sign true RESOURCE LEVELING (letting the overall
project timeline extend, since fixed resources can't be smoothed within
existing float) would be needed instead of smoothing.

Return ONLY a single valid JSON object (no markdown fences, no commentary)
with exactly these keys:

{
  "recommendations": [
    {"task": "task name", "delay_days": integer >= 0, "rationale": "1 sentence, plain language"}
  ],
  "leveling_needed": true or false,
  "summary": "2-4 sentences: what was done, whether smoothing fully resolved the conflicts, and if not, what leveling (timeline extension) would look like instead."
}

Include an entry in "recommendations" for every task you are NOT delaying
too (with delay_days: 0) only if it was involved in a conflict, so the
person can see you considered it. Do not invent tasks that weren't given to
you.
"""


def _tasks_payload(tasks_with_slack: pd.DataFrame) -> list[dict]:
    cols = ["Task", "Resource", "Start Date", "Duration (days)", "Demand", "Deadline", "Planned Finish", "Slack (days)"]
    out = []
    for _, row in tasks_with_slack.iterrows():
        out.append(
            {
                "task": row["Task"],
                "resource": row["Resource"],
                "start_date": str(pd.Timestamp(row["Start Date"]).date()),
                "duration_days": row["Duration (days)"],
                "demand_per_day": row["Demand"],
                "deadline": str(pd.Timestamp(row["Deadline"]).date()),
                "planned_finish": str(pd.Timestamp(row["Planned Finish"]).date()),
                "slack_days": int(row["Slack (days)"]),
            }
        )
    return out


def get_smoothing_recommendations(
    tasks_with_slack: pd.DataFrame,
    resources_df: pd.DataFrame,
    conflict_summary: pd.DataFrame,
    provider: str,
    api_key: str,
    model: str,
    base_url: str = "",
) -> dict:
    """Calls the selected AI provider and returns a dict with keys:
    recommendations (list of dicts), leveling_needed (bool), summary (str).
    Raises RuntimeError on any failure so the Streamlit layer can show it
    directly."""

    payload = {
        "tasks": _tasks_payload(tasks_with_slack),
        "resources": resources_df.to_dict(orient="records"),
        "conflicts": conflict_summary.to_dict(orient="records"),
    }

    prompt = PROMPT_INSTRUCTIONS + "\n\nScheduling data:\n" + json.dumps(payload, indent=2)

    data = parse_json_reply(call_llm(provider, model, api_key, prompt, base_url))
    data.setdefault("recommendations", [])
    data.setdefault("leveling_needed", False)
    data.setdefault("summary", "")
    return data
