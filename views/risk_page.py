import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import data
from core.risks import RISK_COLS, score, suggest_items


def render(ai):
    st.title("Risks and Opportunities")
    st.write("Register with probability x impact scoring, a heat map, response actions and outcomes. Preloaded with the IoT project's register.")

    if "risk_df" not in st.session_state:
        st.session_state.risk_df = data.risks()

    st.subheader("1. Register (editable)")
    edited = st.data_editor(
        st.session_state.risk_df, num_rows="dynamic", key="risk_editor",
        column_config={
            "Type": st.column_config.SelectboxColumn(options=["Risk", "Opportunity"], required=True),
            "Probability (1-5)": st.column_config.NumberColumn(min_value=1, max_value=5, step=1, required=True),
            "Impact (1-5)": st.column_config.NumberColumn(min_value=1, max_value=5, step=1, required=True),
        })
    st.session_state.risk_df = edited
    reg = score(edited)

    k = st.columns(4)
    risks_only = reg[reg["Type"] == "Risk"]
    k[0].metric("Risks", len(risks_only))
    k[1].metric("Opportunities", int((reg["Type"] == "Opportunity").sum()))
    k[2].metric("High-rated risks", int((risks_only["Rating"] == "High").sum()))
    k[3].metric("Occurred", int(risks_only["Outcome"].astype(str).str.startswith("Occurred").sum()))

    st.subheader("2. Heat map")
    kind = st.radio("Show", ["Risk", "Opportunity"], horizontal=True)
    sub = reg[reg["Type"] == kind]
    z = np.outer(np.arange(1, 6), np.arange(1, 6))
    text = [["" for _ in range(5)] for _ in range(5)]
    for _, r in sub.iterrows():
        i, j = int(r["Impact (1-5)"]) - 1, int(r["Probability (1-5)"]) - 1
        text[i][j] = (text[i][j] + " " + str(r["ID"])).strip()
    fig = go.Figure(go.Heatmap(z=z, x=[1, 2, 3, 4, 5], y=[1, 2, 3, 4, 5], text=text, texttemplate="%{text}",
                               colorscale=[[0, "#d1fae5"], [0.35, "#fef3c7"], [1, "#fecaca"]] if kind == "Risk" else [[0, "#e0f2fe"], [1, "#86efac"]],
                               showscale=False, hoverinfo="skip"))
    fig.update_layout(height=380, xaxis_title="Probability", yaxis_title="Impact", margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig)

    st.subheader("3. Ranked by exposure")
    ranked = reg.sort_values("Exposure", ascending=False)[["ID", "Type", "Description", "Exposure", "Rating", "Response strategy", "Outcome"]]
    st.dataframe(ranked, hide_index=True)
    st.caption("Exposure = probability x impact (1 to 25). Low below 6, Medium 6 to 14, High 15 and above.")

    st.subheader("4. AI suggestions")
    st.write("Ask the AI for additional risks or opportunities that are not yet in the register.")
    if st.button(f"Suggest more with {ai.provider}"):
        if not ai.ready:
            st.error(ai.missing_message())
        else:
            try:
                with st.spinner("Asking the AI..."):
                    st.session_state.risk_suggest = suggest_items(
                        edited, data.charter_sample()["inputs"]["description"], ai.provider, ai.api_key, ai.model, ai.base_url)
            except RuntimeError as exc:
                st.error(str(exc))
    items = st.session_state.get("risk_suggest")
    if items:
        st.dataframe(pd.DataFrame(items), hide_index=True)
        if st.button("Add these to the register"):
            n = len(edited)
            rows = []
            for i, it in enumerate(items, 1):
                kind_ = "Opportunity" if str(it.get("type", "Risk")).lower().startswith("opp") else "Risk"
                rows.append({"ID": f"{'O' if kind_ == 'Opportunity' else 'R'}{n + i}", "Type": kind_, "Description": it.get("description", ""),
                             "Probability (1-5)": int(it.get("probability", 3)), "Impact (1-5)": int(it.get("impact", 3)),
                             "Response strategy": it.get("strategy", ""), "Response action": it.get("action", ""), "Outcome": "Open"})
            st.session_state.risk_df = pd.concat([edited, pd.DataFrame(rows)], ignore_index=True)
            st.session_state.risk_suggest = None
            st.rerun()
