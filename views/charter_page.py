import os
import tempfile
from datetime import date

import streamlit as st

from core import data
from core.charter import build_charter_xlsx, generate_charter_content

TEMPLATE = os.path.join(data.ASSETS, "Project_Charter_Template.xlsx")


def _pipe_lines(text, k1, k2):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|", 1)]
        out.append({k1: parts[0], k2: parts[1] if len(parts) > 1 else ""})
    return out


def render(ai):
    st.title("Project Charter")
    st.write("Fill in the basics, let the AI draft the charter, review and edit, then download it in your template's format. Preloaded with the IoT project.")
    sample = data.charter_sample()
    s = sample["inputs"]
    ver = st.session_state.setdefault("charter_ver", 0)
    st.session_state.setdefault("charter_content", None)
    st.session_state.setdefault("charter_file", None)

    st.subheader("1. Project basics")
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Project Name*", s["project_name"], key="ch_name")
        pm = st.text_input("Project Manager(s)*", s["project_manager"], key="ch_pm")
        budget = st.text_input("Budget", s["budget"], key="ch_budget")
    with c2:
        timeframe = st.text_input("Target Timeframe", s["timeframe"], key="ch_time")
        team = st.text_area("Team Members (one per line)", s["team_members"], height=90, key="ch_team")
    desc = st.text_area("Project Description / Purpose*", s["description"], height=140, key="ch_desc")
    stake_raw = st.text_area("Known Stakeholders (optional, one per line as Name - Role)", s["stakeholders_raw"], height=80, key="ch_stake")

    ok = bool(name and pm and desc)
    b1, b2 = st.columns(2)
    gen = b1.button("Generate charter content with AI", type="primary", disabled=not ok)
    load = b2.button("Load the prepared sample draft (no AI)")

    if load:
        st.session_state.charter_content = sample["content"]
        st.session_state.charter_file = None
        st.session_state.charter_ver = ver + 1
        st.rerun()
    if gen:
        if not ai.ready:
            st.error(ai.missing_message())
        else:
            inputs = dict(project_name=name, project_manager=pm, description=desc, budget=budget,
                          team_members=team, stakeholders_raw=stake_raw, timeframe=timeframe)
            with st.spinner(f"Asking {ai.provider} to draft the charter..."):
                try:
                    st.session_state.charter_content = generate_charter_content(inputs, ai.provider, ai.api_key, ai.model, ai.base_url)
                    st.session_state.charter_file = None
                    st.session_state.charter_ver = ver + 1
                    st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc))

    content = st.session_state.charter_content
    if content:
        v = st.session_state.charter_ver
        st.subheader("2. Review and edit the draft")
        objective = st.text_area("Objective", content.get("objective", ""), height=80, key=f"ob{v}")
        success = st.text_area("Success Criteria", content.get("success_criteria", ""), height=80, key=f"sc{v}")
        deliver = st.text_area("Key Deliverables", content.get("key_deliverables", ""), height=110, key=f"kd{v}")
        st.markdown("**High Level Requirements** (one per line)")
        reqs = st.text_area("Requirements", "\n".join(content.get("high_level_requirements", [])), height=110, label_visibility="collapsed", key=f"rq{v}")
        st.markdown("**Milestones and Deadlines** (one per line: `Milestone | Deadline`)")
        ms = st.text_area("Milestones", "\n".join(f"{m.get('milestone','')} | {m.get('deadline','')}" for m in content.get("milestones", [])), height=120, label_visibility="collapsed", key=f"ms{v}")
        st.markdown("**Risks** (one per line)")
        risks = st.text_area("Risks", "\n".join(content.get("risks", [])), height=100, label_visibility="collapsed", key=f"rk{v}")
        st.markdown("**Stakeholders** (one per line: `Name | Role`)")
        sh = st.text_area("Stakeholders", "\n".join(f"{x.get('name','')} | {x.get('role','')}" for x in content.get("stakeholders", [])), height=100, label_visibility="collapsed", key=f"sh{v}")
        a1, a2 = st.columns(2)
        with a1:
            appr_name = st.text_input("Approver Name", pm, key="ch_an")
            appr_title = st.text_input("Approver Title", "", key="ch_at")
        with a2:
            appr_date = st.text_input("Date", date.today().strftime("%B %d, %Y"), key="ch_ad")
        st.divider()
        if st.button("Build final charter file"):
            final = dict(project_name=name, project_manager=pm, budget=budget, team_members=team, objective=objective,
                         success_criteria=success, key_deliverables=deliver,
                         high_level_requirements=[x.strip() for x in reqs.splitlines() if x.strip()],
                         milestones=_pipe_lines(ms, "milestone", "deadline"),
                         risks=[x.strip() for x in risks.splitlines() if x.strip()],
                         stakeholders=_pipe_lines(sh, "name", "role"),
                         approval_name=appr_name, approval_title=appr_title, approval_date=appr_date)
            out = os.path.join(tempfile.gettempdir(), "Generated_Project_Charter.xlsx")
            st.session_state.charter_file = build_charter_xlsx(final, TEMPLATE, out)
            st.success("Charter file built. Download it below.")

    path = st.session_state.charter_file
    if path and os.path.exists(path):
        st.subheader("3. Download")
        with open(path, "rb") as f:
            st.download_button("Download Project Charter (.xlsx)", f.read(),
                               file_name=f"{(name or 'Project').replace(' ', '_')}_Charter.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
