"""
scheduler.py
------------
Pure, deterministic scheduling logic - no AI involved. This is the "code a
scheduler that checks if resource demand exceeds availability" part of the
assignment.

Responsibilities:
  - build_demand_profile(): for every resource, work out total demand vs
    available capacity on every day of the project.
  - detect_conflicts(): scan that profile for days where demand > capacity.
  - compute_slack(): work out how many days each task could slip without
    missing its own deadline (its "float") - this is what the AI step later
    uses to decide which tasks are safe to delay (smoothing).
  - apply_delays(): shift task start dates by AI-recommended (or manual)
    delays and return the updated task table.
"""

from __future__ import annotations

import pandas as pd


REQUIRED_TASK_COLS = ["Task", "Resource", "Start Date", "Duration (days)", "Demand", "Deadline"]
REQUIRED_RESOURCE_COLS = ["Resource", "Daily Capacity"]


def _to_date(x):
    result = pd.to_datetime(x)
    if isinstance(result, pd.Series):
        return result.dt.normalize()
    return result.normalize()


def validate_inputs(tasks_df: pd.DataFrame, resources_df: pd.DataFrame) -> list[str]:
    """Returns a list of human-readable problems (empty list = all good)."""
    problems = []

    for col in REQUIRED_TASK_COLS:
        if col not in tasks_df.columns:
            problems.append(f"Tasks table is missing column '{col}'.")
    for col in REQUIRED_RESOURCE_COLS:
        if col not in resources_df.columns:
            problems.append(f"Resources table is missing column '{col}'.")

    if problems:
        return problems

    if tasks_df["Task"].isna().any() or (tasks_df["Task"].astype(str).str.strip() == "").any():
        problems.append("Every task needs a name.")

    known_resources = set(resources_df["Resource"].astype(str).str.strip())
    used_resources = set(tasks_df["Resource"].astype(str).str.strip())
    unknown = used_resources - known_resources
    if unknown:
        problems.append(f"Task(s) reference resource(s) not in the Resources table: {', '.join(sorted(unknown))}")

    for _, row in tasks_df.iterrows():
        try:
            dur = float(row["Duration (days)"])
            if dur <= 0:
                problems.append(f"Task '{row['Task']}' must have a positive duration.")
        except (ValueError, TypeError):
            problems.append(f"Task '{row['Task']}' has a non-numeric duration.")
        try:
            float(row["Demand"])
        except (ValueError, TypeError):
            problems.append(f"Task '{row['Task']}' has a non-numeric demand.")

    return problems


def compute_slack(tasks_df: pd.DataFrame) -> pd.DataFrame:
    """Adds Planned Finish and Slack (days) columns.

    Slack = how many days the task's start could move later and still
    finish on/before its Deadline. Negative slack means the task is already
    projected to miss its deadline as scheduled.
    """
    df = tasks_df.copy()
    df["Start Date"] = _to_date(df["Start Date"])
    df["Deadline"] = _to_date(df["Deadline"])
    df["Duration (days)"] = df["Duration (days)"].astype(float)
    df["Planned Finish"] = df["Start Date"] + pd.to_timedelta(df["Duration (days)"] - 1, unit="D")
    df["Slack (days)"] = (df["Deadline"] - df["Planned Finish"]).dt.days
    return df


def build_demand_profile(tasks_df: pd.DataFrame, resources_df: pd.DataFrame) -> pd.DataFrame:
    """Returns a long-format DataFrame: Date, Resource, Demand, Capacity, Overallocation."""
    tasks_df = tasks_df.copy()
    tasks_df["Start Date"] = _to_date(tasks_df["Start Date"])
    tasks_df["Duration (days)"] = tasks_df["Duration (days)"].astype(float)
    tasks_df["Demand"] = tasks_df["Demand"].astype(float)

    if tasks_df.empty:
        return pd.DataFrame(columns=["Date", "Resource", "Demand", "Capacity", "Overallocation"])

    horizon_start = tasks_df["Start Date"].min()
    horizon_end = (tasks_df["Start Date"] + pd.to_timedelta(tasks_df["Duration (days)"] - 1, unit="D")).max()
    all_dates = pd.date_range(horizon_start, horizon_end, freq="D")

    capacity_map = dict(zip(resources_df["Resource"].astype(str).str.strip(), resources_df["Daily Capacity"].astype(float)))

    records = []
    for resource, cap in capacity_map.items():
        demand_by_date = {d: 0.0 for d in all_dates}
        res_tasks = tasks_df[tasks_df["Resource"].astype(str).str.strip() == resource]
        for _, t in res_tasks.iterrows():
            task_dates = pd.date_range(t["Start Date"], periods=int(t["Duration (days)"]), freq="D")
            for d in task_dates:
                demand_by_date[d] = demand_by_date.get(d, 0.0) + t["Demand"]
        for d in all_dates:
            demand = demand_by_date[d]
            records.append(
                {
                    "Date": d,
                    "Resource": resource,
                    "Demand": demand,
                    "Capacity": cap,
                    "Overallocation": max(0.0, demand - cap),
                }
            )

    return pd.DataFrame.from_records(records)


def detect_conflicts(profile: pd.DataFrame, tasks_df: pd.DataFrame) -> pd.DataFrame:
    """Returns one row per (date, resource) where demand exceeds capacity,
    including which tasks are contributing to that day's demand."""
    if profile.empty:
        return pd.DataFrame(columns=["Date", "Resource", "Demand", "Capacity", "Overallocation", "Contributing Tasks"])

    conflicts = profile[profile["Overallocation"] > 0].copy()
    if conflicts.empty:
        return conflicts.assign(**{"Contributing Tasks": []})

    tasks_df = tasks_df.copy()
    tasks_df["Start Date"] = _to_date(tasks_df["Start Date"])
    tasks_df["Duration (days)"] = tasks_df["Duration (days)"].astype(float)
    tasks_df["End Date"] = tasks_df["Start Date"] + pd.to_timedelta(tasks_df["Duration (days)"] - 1, unit="D")

    def contributing(row):
        active = tasks_df[
            (tasks_df["Resource"].astype(str).str.strip() == row["Resource"])
            & (tasks_df["Start Date"] <= row["Date"])
            & (tasks_df["End Date"] >= row["Date"])
        ]
        return ", ".join(active["Task"].astype(str).tolist())

    conflicts["Contributing Tasks"] = conflicts.apply(contributing, axis=1)
    return conflicts.sort_values(["Resource", "Date"]).reset_index(drop=True)


def summarize_conflicts(conflicts: pd.DataFrame) -> pd.DataFrame:
    """Collapses the day-by-day conflicts into one row per resource: how many
    conflict-days, the worst overallocation, and every task involved. This is
    the compact version we hand to the AI (day-by-day would be too verbose)."""
    if conflicts.empty:
        return pd.DataFrame(columns=["Resource", "Conflict Days", "Peak Overallocation", "Tasks Involved"])

    rows = []
    for resource, grp in conflicts.groupby("Resource"):
        tasks_involved = set()
        for t in grp["Contributing Tasks"]:
            tasks_involved.update(x.strip() for x in t.split(",") if x.strip())
        rows.append(
            {
                "Resource": resource,
                "Conflict Days": len(grp),
                "Peak Overallocation": grp["Overallocation"].max(),
                "Tasks Involved": ", ".join(sorted(tasks_involved)),
            }
        )
    return pd.DataFrame(rows)


def apply_delays(tasks_df: pd.DataFrame, delays: dict[str, int]) -> pd.DataFrame:
    """delays: {task_name: delay_in_days}. Returns a new tasks_df with Start
    Date (and therefore Planned Finish) shifted for the named tasks."""
    df = tasks_df.copy()
    df["Start Date"] = _to_date(df["Start Date"])
    for task_name, delay_days in delays.items():
        mask = df["Task"].astype(str).str.strip() == str(task_name).strip()
        df.loc[mask, "Start Date"] = df.loc[mask, "Start Date"] + pd.to_timedelta(int(delay_days), unit="D")
    return df
