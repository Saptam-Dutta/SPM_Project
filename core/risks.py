"""risks.py - risk register scoring, a probability x impact matrix, and an
AI helper that suggests extra risks/opportunities with responses."""
import json

import pandas as pd

from .llm_client import call_llm, parse_json_reply

RISK_COLS = ["ID", "Type", "Description", "Probability (1-5)", "Impact (1-5)", "Response strategy", "Response action", "Outcome"]


def score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Probability (1-5)"] = pd.to_numeric(df["Probability (1-5)"], errors="coerce").fillna(1).clip(1, 5)
    df["Impact (1-5)"] = pd.to_numeric(df["Impact (1-5)"], errors="coerce").fillna(1).clip(1, 5)
    df["Exposure"] = (df["Probability (1-5)"] * df["Impact (1-5)"]).astype(int)
    df["Rating"] = pd.cut(df["Exposure"], bins=[0, 5, 14, 25], labels=["Low", "Medium", "High"])
    return df


SUGGEST_PROMPT = """
You are a project risk analyst. Given the project description and the risks
already in the register, suggest up to 5 ADDITIONAL items (risks or
opportunities) that are NOT already covered, each with a probability and
impact on a 1-5 scale, a response strategy and a concrete response action.

Risk strategies: Avoid, Mitigate, Transfer, Accept. Opportunity strategies:
Exploit, Enhance, Share, Accept.

Return ONLY one valid JSON object (no markdown fences) with this shape:
{"items": [{"type": "Risk" or "Opportunity", "description": "...",
"probability": 1-5, "impact": 1-5, "strategy": "...", "action": "..."}]}
"""


def suggest_items(register: pd.DataFrame, project_text: str, provider, api_key, model, base_url="") -> list[dict]:
    existing = register[["ID", "Type", "Description"]].to_dict(orient="records")
    prompt = SUGGEST_PROMPT + "\n\nProject:\n" + project_text + "\n\nExisting register:\n" + json.dumps(existing, indent=2)
    data = parse_json_reply(call_llm(provider, model, api_key, prompt, base_url))
    return list(data.get("items", []))
