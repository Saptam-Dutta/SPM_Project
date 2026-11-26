import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import data
from core.evm import forecast, generate_ai_report, prepare


def render(ai):
    st.title("Cost and Earned Value (EVM)")
    st.write("Earned value metrics, Isolation Forest anomaly detection and an AI risk report. Preloaded with the IoT project's status checks (0/100 earned-value rule).")

    up = st.file_uploader("Upload your own EVM CSV (columns: Period or Sprint or Day, PV, EV, AC)", type=["csv"])
    raw = pd.read_csv(up) if up is not None else data.evm()
    try:
        df = prepare(raw)
    except ValueError as exc:
        st.error(str(exc))
        return

    bac = st.number_input("Budget at completion (BAC)", min_value=1.0, value=33000.0, step=1000.0, help="Revised budget: 33 person-days x Rs 1,000")
    fc = forecast(df, bac)
    m = st.columns(6)
    m[0].metric("Periods", len(df))
    m[1].metric("SPI (latest)", f"{fc['SPI']:.2f}")
    m[2].metric("CPI (latest)", f"{fc['CPI']:.2f}")
    m[3].metric("EAC = BAC / CPI", f"{fc['EAC']:,.0f}")
    m[4].metric("VAC = BAC - EAC", f"{fc['VAC']:,.0f}")
    m[5].metric("Flagged anomalies", int((df["Status"] == "ANOMALY").sum()))
    st.caption("SV = EV - PV, SPI = EV / PV, CV = EV - AC, CPI = EV / AC. At completion SV is 0 when all planned work is done.")

    st.subheader("Results")
    cols = ["Period", "PV", "EV", "AC", "CV", "SV", "CPI", "SPI", "Status"]
    st.dataframe(df[cols].round({"CPI": 3, "SPI": 3}), hide_index=True)

    st.subheader("Earned value curve")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Period"], y=df["PV"], name="PV", line=dict(color="#6b7280", width=3)))
    fig.add_trace(go.Scatter(x=df["Period"], y=df["EV"], name="EV", line=dict(color="#2563eb", width=3, shape="hv")))
    fig.add_trace(go.Scatter(x=df["Period"], y=df["AC"], name="AC", line=dict(color="#eb6834", width=3, dash="dash")))
    an = df[df["Status"] == "ANOMALY"]
    if not an.empty:
        fig.add_trace(go.Scatter(x=an["Period"], y=an["EV"], mode="markers", name="Anomaly", marker=dict(size=13, color="#d62728", symbol="x")))
    fig.update_layout(height=380, margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", y=1.08))
    st.plotly_chart(fig)

    l, r = st.columns(2)
    with l:
        st.markdown("**CPI and SPI**")
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=df["Period"], y=df["CPI"], name="CPI"))
        f2.add_trace(go.Scatter(x=df["Period"], y=df["SPI"], name="SPI"))
        f2.add_hline(y=1.0, line_dash="dot", line_color="gray")
        f2.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(f2)
    with r:
        st.markdown("**Cost and schedule variance**")
        f3 = go.Figure()
        f3.add_trace(go.Bar(x=df["Period"], y=df["CV"], name="CV"))
        f3.add_trace(go.Bar(x=df["Period"], y=df["SV"], name="SV"))
        f3.update_layout(height=300, barmode="group", margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(f3)

    st.subheader("Anomaly review")
    if len(df) < 5:
        st.info("Anomaly detection needs at least 5 rows.")
    elif an.empty:
        st.info("No records were flagged by Isolation Forest.")
    else:
        st.dataframe(an[cols].round({"CPI": 3, "SPI": 3}), hide_index=True)
    st.caption("An anomaly is a statistical flag that requires investigation; it does not prove the data is wrong.")

    st.divider()
    st.subheader("AI risk analysis")
    if st.button(f"Generate AI report with {ai.provider}", type="primary"):
        if not ai.ready:
            st.warning(ai.missing_message())
        elif an.empty:
            st.info("There are no flagged anomalies to send for analysis.")
        else:
            try:
                with st.spinner("Generating your risk report..."):
                    report = generate_ai_report(ai.provider, ai.api_key, ai.model, an, ai.base_url)
                st.markdown("### Generated risk report")
                st.markdown(report)
            except Exception as exc:
                st.error("The AI request could not be completed.")
                with st.expander("Technical error details"):
                    st.code(str(exc))
