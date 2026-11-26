"""
leveling.py
-----------
Rule-based (no AI) resource smoothing and resource leveling, so the Schedule
page works even without an API key and the AI advice can be checked against
a deterministic answer.

  * smooth():  delay tasks ONLY inside their slack (deadlines stay safe).
               A delay is accepted only if it strictly reduces the total
               overallocation. If nothing helps, smoothing cannot fix it.
  * level():   resource leveling. Tasks may slip past their deadline and the
               project end date may move. Respects the optional
               "Depends On" column (finish-to-start).
"""
from __future__ import annotations

import pandas as pd

from .scheduler import build_demand_profile, compute_slack


def _total_overallocation(tasks_df: pd.DataFrame, resources_df: pd.DataFrame) -> float:
    profile = build_demand_profile(tasks_df, resources_df)
    return float(profile["Overallocation"].sum()) if not profile.empty else 0.0


def _shift(tasks_df: pd.DataFrame, task: str, days: int) -> pd.DataFrame:
    df = tasks_df.copy()
    df["Start Date"] = pd.to_datetime(df["Start Date"]).dt.normalize()
    mask = df["Task"].astype(str).str.strip() == str(task).strip()
    df.loc[mask, "Start Date"] = df.loc[mask, "Start Date"] + pd.to_timedelta(days, unit="D")
    return df


def smooth(tasks_df: pd.DataFrame, resources_df: pd.DataFrame, max_rounds: int = 50) -> dict:
    """Greedy resource smoothing within slack. Returns
    {"delays": {task: days}, "before": float, "after": float}."""
    work = tasks_df.copy()
    slack = compute_slack(work).set_index(work["Task"].astype(str).str.strip())["Slack (days)"].to_dict()
    delays: dict[str, int] = {}
    before = current = _total_overallocation(work, resources_df)
    for _ in range(max_rounds):
        if current <= 0:
            break
        best = None  # (overallocation, delay, task)
        for name, sl in slack.items():
            room = int(sl) - delays.get(name, 0)
            for step in range(1, max(room, 0) + 1):
                trial = _total_overallocation(_shift(work, name, step), resources_df)
                if trial < current and (best is None or (trial, step) < (best[0], best[1])):
                    best = (trial, step, name)
        if best is None:
            break
        current, step, name = best
        work = _shift(work, name, step)
        delays[name] = delays.get(name, 0) + step
    return {"delays": delays, "before": before, "after": current}


def _tokens(task_name: str) -> set[str]:
    name = str(task_name).strip()
    first = name.replace(":", " ").split(" ")[0]
    return {name, first}


def level(tasks_df: pd.DataFrame, resources_df: pd.DataFrame) -> pd.DataFrame:
    """Serial resource leveling. Returns a copy of tasks_df with new Start
    Dates, plus Delay (days) and Leveled Finish columns."""
    df = compute_slack(tasks_df).reset_index(drop=True)
    cap = dict(zip(resources_df["Resource"].astype(str).str.strip(), resources_df["Daily Capacity"].astype(float)))
    origin = df["Start Date"].min()
    df["_s"] = (df["Start Date"] - origin).dt.days
    df["_d"] = df["Duration (days)"].astype(int)
    df["_slack"] = df["Slack (days)"]
    order = df.sort_values(["_s", "_slack"]).index.tolist()

    usage: dict[str, dict[int, float]] = {}
    new_start: dict[int, int] = {}
    for i in order:
        row = df.loc[i]
        res = str(row["Resource"]).strip()
        demand = float(row["Demand"])
        earliest = int(row["_s"])
        deps = [t.strip() for t in str(row.get("Depends On", "") or "").split(",") if t.strip()]
        for j, other in df.iterrows():
            if j in new_start and any(dep in _tokens(other["Task"]) for dep in deps):
                earliest = max(earliest, new_start[j] + int(other["_d"]))
        day_usage = usage.setdefault(res, {})
        limit = cap.get(res, float("inf"))
        start = earliest
        while demand <= limit and any(day_usage.get(d, 0.0) + demand > limit + 1e-9 for d in range(start, start + int(row["_d"]))):
            start += 1
        for d in range(start, start + int(row["_d"])):
            day_usage[d] = day_usage.get(d, 0.0) + demand
        new_start[i] = start

    out = tasks_df.copy().reset_index(drop=True)
    out["Start Date"] = [origin + pd.Timedelta(days=new_start[i]) for i in range(len(out))]
    out["Delay (days)"] = [new_start[i] - int(df.loc[i, "_s"]) for i in range(len(out))]
    out["Leveled Finish"] = out["Start Date"] + pd.to_timedelta(out["Duration (days)"].astype(float) - 1, unit="D")
    return out


def project_finish(tasks_df: pd.DataFrame):
    df = compute_slack(tasks_df)
    return df["Planned Finish"].max()
