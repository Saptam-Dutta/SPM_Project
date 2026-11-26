"""data.py - loads the sample IoT project data shipped in /data."""
import json
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
ASSETS = os.path.join(ROOT, "assets")


def _csv(name, **kw):
    return pd.read_csv(os.path.join(DATA, name), **kw)


def tasks() -> pd.DataFrame:
    df = _csv("tasks.csv")
    df["Start Date"] = pd.to_datetime(df["Start Date"]).dt.normalize()
    df["Deadline"] = pd.to_datetime(df["Deadline"]).dt.normalize()
    df["Depends On"] = df["Depends On"].fillna("")
    return df


def resources() -> pd.DataFrame:
    return _csv("resources.csv")


def evm() -> pd.DataFrame:
    return _csv("evm_data.csv")


def risks() -> pd.DataFrame:
    return _csv("risks.csv")


def defects() -> pd.DataFrame:
    return _csv("defects.csv")


def plan_vs_actual() -> pd.DataFrame:
    df = _csv("plan_vs_actual.csv")
    for c in ("Plan start", "Plan finish", "Actual start", "Actual finish"):
        df[c] = pd.to_datetime(df[c])
    return df


def charter_sample() -> dict:
    with open(os.path.join(DATA, "charter_sample.json"), encoding="utf-8") as f:
        return json.load(f)
