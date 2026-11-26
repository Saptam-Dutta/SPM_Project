import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core import data
from core.evm import calculate_evm


def render(ai):
    st.title("IoT Device Security Monitoring System")
    st.caption("Software Project Management control centre: charter, schedule, cost and risk for the 7th semester project.")

    pva = data.plan_vs_actual()
    base = pva[pva["Kind"] == "Baseline"]
    changes = pva[pva["Kind"] != "Baseline"]
    plan_base, plan_all, actual_all = int(base["Plan days"].sum()), int(pva["Plan days"].sum()), int(pva["Actual days"].sum())
    rate = 1000

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Original plan (Rs {plan_base * rate:,})", f"{plan_base} days")
    c2.metric(f"Revised plan, +{len(changes)} changes (Rs {plan_all * rate:,})", f"{plan_all} days")
    c3.metric("Actual", f"{actual_all} days", f"{actual_all - plan_all:+d} days vs revised", delta_color="inverse")
    c4.metric("Actual cost", f"Rs {actual_all * rate:,}", f"{(actual_all - plan_all) * rate:+,} Rs vs revised", delta_color="inverse")
    st.caption("Effort in person-days (1 person-day = 6 productive hours) at Rs 1,000 per person-day. Day 1 = 1 Oct 2026.")

    st.subheader("Schedule: plan against actual")
    rows = []
    for _, r in pva.iterrows():
        label = f"{r['ID']} {r['Activity']}"
        rows.append({"Activity": label, "Series": "Plan", "Start": r["Plan start"], "Finish": r["Plan finish"] + pd.Timedelta(days=1)})
        rows.append({"Activity": label, "Series": "Actual", "Start": r["Actual start"], "Finish": r["Actual finish"] + pd.Timedelta(days=1)})
    gantt = pd.DataFrame(rows)
    fig = px.timeline(gantt, x_start="Start", x_end="Finish", y="Activity", color="Series",
                      color_discrete_map={"Plan": "#9aa3b2", "Actual": "#2563eb"})
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(title=None)
    fig.update_layout(barmode="group", height=620, margin=dict(t=40, b=10, l=10, r=10), legend=dict(orientation="h", y=1.03, yanchor="bottom"))
    st.plotly_chart(fig)

    left, right = st.columns(2)
    with left:
        st.subheader("Earned value at completion")
        df = calculate_evm(data.evm().rename(columns={"Period": "Period"}))
        last = df.iloc[-1]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("SV", f"{last['SV']:,.0f}")
        m2.metric("SPI", f"{last['SPI']:.2f}")
        m3.metric("CV", f"{last['CV']:,.0f}")
        m4.metric("CPI", f"{last['CPI']:.2f}")
        st.caption("Final checkpoint (Day 35). At completion SV is 0 because all planned work is done; the delay shows in days (2 late against the revised plan).")
    with right:
        st.subheader("Defects by severity")
        d = data.defects()
        counts = d["Severity"].value_counts().reindex(["High", "Medium", "Low"]).fillna(0).reset_index()
        counts.columns = ["Severity", "Defects"]
        figd = px.bar(counts, x="Severity", y="Defects", text="Defects", color_discrete_sequence=["#2563eb"])
        figd.update_layout(height=260, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(figd)
    with st.expander("All 12 defects and fixes"):
        st.dataframe(d, hide_index=True)

    st.info("Use the pages in the sidebar: Charter, Schedule and resources, Cost (EVM), Risks. All of them are preloaded with this project and use the AI provider chosen in the sidebar.")
