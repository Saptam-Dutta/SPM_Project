"""evm.py - EVM maths and anomaly detection (from the EVM anomaly app) plus
the AI report prompt, now using the shared provider client."""
import pandas as pd
from sklearn.ensemble import IsolationForest

from .llm_client import call_llm


def calculate_evm(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["CV"] = df["EV"] - df["AC"]
    df["SV"] = df["EV"] - df["PV"]
    df["CPI"] = df["EV"] / df["AC"]
    df["SPI"] = df["EV"] / df["PV"]
    return df


def detect_anomalies(df: pd.DataFrame, contamination: float = 0.1) -> pd.DataFrame:
    df = df.copy()
    features = ["CV", "SV", "CPI", "SPI"]
    model = IsolationForest(contamination=contamination, random_state=42)
    df["Anomaly"] = model.fit_predict(df[features])
    df["Status"] = df["Anomaly"].map({1: "NORMAL", -1: "ANOMALY"})
    return df


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Validate a raw table and return it with a 'Period' column, numeric
    PV/EV/AC, and EVM metrics. Raises ValueError with a readable message."""
    df = df.copy()
    for name in ("Period", "Sprint", "Day", "Week", "Month"):
        if name in df.columns:
            df = df.rename(columns={name: "Period"})
            break
    missing = [c for c in ("Period", "PV", "EV", "AC") if c not in df.columns]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing) + " (need Period/Sprint/Day, PV, EV, AC)")
    if df.empty:
        raise ValueError("The table has no data rows.")
    for c in ("PV", "EV", "AC"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if df[["PV", "EV", "AC"]].isna().any().any():
        raise ValueError("PV, EV and AC must contain valid numbers.")
    if (df["PV"] <= 0).any() or (df["AC"] <= 0).any():
        raise ValueError("PV and AC must be greater than zero.")
    df = calculate_evm(df)
    if len(df) >= 5:
        df = detect_anomalies(df)
    else:
        df["Status"] = "NORMAL"
    return df


def forecast(df: pd.DataFrame, bac: float) -> dict:
    last = df.iloc[-1]
    cpi = float(last["CPI"])
    eac = bac / cpi if cpi > 0 else float("inf")
    return {"BAC": bac, "EAC": eac, "VAC": bac - eac, "CPI": cpi, "SPI": float(last["SPI"])}


def generate_ai_report(provider, api_key, model, anomalies: pd.DataFrame, base_url: str = "") -> str:
    if anomalies.empty:
        raise ValueError("There are no flagged anomalies to analyze.")
    columns = ["Period", "PV", "EV", "AC", "CV", "SV", "CPI", "SPI", "Status"]
    data = anomalies[columns].round({"CPI": 3, "SPI": 3}).to_string(index=False)
    prompt = f"""
You are an Earned Value Management analyst.

Analyze these EVM records flagged by Isolation Forest:

{data}

Write a professional report containing:
1. Executive summary.
2. Cost and schedule variance analysis.
3. CPI and SPI interpretation.
4. Main project risks.
5. Recommended corrective actions.

Use only the supplied data. Explain that a statistical anomaly
is a signal to investigate, not proof of fraud or error.
Keep the report concise and suitable for a college assignment.
"""
    result = call_llm(provider, model, api_key, prompt, base_url)
    if not result.strip():
        raise ValueError("The model returned an empty response.")
    return result
