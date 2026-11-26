"""
SPM Project Control Centre
--------------------------
One Streamlit app that combines the three course apps:
  * Project Charter generator        (charter app)
  * Schedule and resource conflicts  (resource conflict detection app)
  * Cost / EVM anomaly detection     (EVM app)
plus a Risks and Opportunities register, all preloaded with the
IoT Device Security Monitoring System project and sharing ONE AI provider
setting (Gemini, OpenAI, Anthropic Claude, or any OpenAI-compatible API).

Run:  streamlit run app.py
"""
import os

import streamlit as st

from core.llm_client import PROVIDER_MODELS
from views import charter_page, cost_page, overview, risk_page, schedule_page
from views.common import AIConfig

st.set_page_config(page_title="SPM Project Control Centre", layout="wide")

PAGES = {
    "Overview": overview.render,
    "Charter": charter_page.render,
    "Schedule and resources": schedule_page.render,
    "Cost (EVM)": cost_page.render,
    "Risks": risk_page.render,
}

with st.sidebar:
    st.title("SPM Control Centre")
    page = st.radio("Page", list(PAGES.keys()), label_visibility="collapsed")
    st.divider()
    st.subheader("AI provider (all pages)")
    provider = st.selectbox("Provider", list(PROVIDER_MODELS.keys()))
    env_name = f"{provider.upper().replace(' ', '_').replace('-', '_')}_API_KEY"
    api_key = st.text_input(f"{provider} API key", type="password",
                            help="Kept only in this browser session, never written to disk.",
                            value=os.environ.get(env_name, ""), key=f"key_{provider}")
    base_url = ""
    if provider == "OpenAI-compatible API":
        base_url = st.text_input("API base URL", placeholder="https://api.openai.com/v1")
        model = st.text_input("Model ID", placeholder="your provider's model ID")
    else:
        model = st.selectbox("Model", PROVIDER_MODELS[provider])
        with st.expander("Or use a different model ID"):
            custom = st.text_input("Custom model ID", value="")
            if custom.strip():
                model = custom.strip()
    st.caption("Everything except the AI buttons works without a key.")

ai = AIConfig(provider=provider, api_key=api_key, model=model, base_url=base_url)
PAGES[page](ai)
