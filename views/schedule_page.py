import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core import data
from core.ai_advisor import get_smoothing_recommendations
from core.leveling import level, project_finish, smooth
from core.scheduler import (apply_delays, build_demand_profile, compute_slack, detect_conflicts,
                            summarize_conflicts, validate_inputs)


def _reset_results():
    for k in ("sch_profile", "sch_conflicts", "sch_summary", "sch_ai", "sch_smooth", "sch_level"):
        st.session_state[k] = None


def render(ai):
    st.title("Schedule and Resource Conflicts")
    st.write("Tasks are placed where their logic allows (parallel where possible). With one person, parallel tasks overload the resource. "
             "The tool detects that, tries smoothing (delays inside slack), and falls back to leveling (extending the timeline).")

    if "sch_tasks" not in st.session_state:
        st.session_state.sch_tasks = data.tasks()
        st.session_state.sch_res = data.resources()
        _reset_results()
        st.session_state.sch_applied = None

    c0, c1 = st.columns([1, 4])
    if c0.button("Reset to project data"):
        st.session_state.sch_tasks = data.tasks()
        st.session_state.sch_res = data.resources()
        _reset_results()
        st.session_state.sch_applied = None
        st.rerun()
    c1.caption("Day numbers are shown as calendar dates (Day 1 = 1 Oct 2026). Dependencies are optional and used by leveling.")

    st.subheader("1. Resources and daily capacity")
    res = st.data_editor(st.session_state.sch_res, num_rows="dynamic", key="sch_res_editor",
                         column_config={"Resource": st.column_config.TextColumn(required=True),
                                        "Daily Capacity": st.column_config.NumberColumn(required=True, min_value=0.0, step=0.5)})
    st.session_state.sch_res = res

    st.subheader("2. Tasks")
    tasks = st.data_editor(st.session_state.sch_tasks, num_rows="dynamic", key="sch_tasks_editor",
                           column_config={"Task": st.column_config.TextColumn(required=True),
                                          "Resource": st.column_config.TextColumn(required=True),
                                          "Start Date": st.column_config.DateColumn(required=True),
                                          "Duration (days)": st.column_config.NumberColumn(required=True, min_value=1, step=1),
                                          "Demand": st.column_config.NumberColumn(required=True, min_value=0.0, step=0.5),
                                          "Deadline": st.column_config.DateColumn(required=True),
                                          "Depends On": st.column_config.TextColumn(help="Comma-separated task IDs, e.g. T7, T8")})
    st.session_state.sch_tasks = tasks

    st.subheader("3. Detect resource conflicts")
    if st.button("Check demand vs availability", type="primary"):
        problems = validate_inputs(tasks, res)
        if problems:
            for p in problems:
                st.error(p)
        else:
            _reset_results()
            prof = build_demand_profile(tasks, res)
            st.session_state.sch_profile = prof
            st.session_state.sch_conflicts = detect_conflicts(prof, tasks)
            st.session_state.sch_summary = summarize_conflicts(st.session_state.sch_conflicts)
            st.session_state.sch_applied = None

    prof = st.session_state.get("sch_profile")
    if prof is not None:
        conflicts, summary = st.session_state.sch_conflicts, st.session_state.sch_summary
        for resource in sorted(prof["Resource"].unique()):
            rp = prof[prof["Resource"] == resource]
            fig = go.Figure()
            fig.add_trace(go.Bar(x=rp["Date"], y=rp["Demand"], name="Demand",
                                 marker_color=["#d62728" if d > c else "#1f77b4" for d, c in zip(rp["Demand"], rp["Capacity"])]))
            fig.add_trace(go.Scatter(x=rp["Date"], y=rp["Capacity"], name="Capacity", mode="lines", line=dict(color="black", dash="dash")))
            fig.update_layout(title=f"{resource}: demand vs capacity", height=300, margin=dict(t=70, b=20, l=20, r=20),
                              legend=dict(orientation="h", yanchor="bottom", y=1.05))
            st.plotly_chart(fig)
        if conflicts.empty:
            st.success("No conflicts: demand stays within capacity every day.")
        else:
            st.warning(f"{len(conflicts)} conflict-day(s) across {summary['Resource'].nunique()} resource(s).")
            st.dataframe(summary, hide_index=True)
            with st.expander("Day-by-day detail"):
                st.dataframe(conflicts[["Date", "Resource", "Demand", "Capacity", "Overallocation", "Contributing Tasks"]], hide_index=True)

            st.subheader("4. Resolve the conflicts")
            logic_finish = project_finish(tasks)
            t1, t2, t3 = st.tabs(["Smoothing (rule-based)", "Smoothing (AI advice)", "Resource leveling"])

            with t1:
                st.write("Delays tasks **only inside their slack**, so no deadline is missed. A delay is accepted only if it reduces the overload.")
                if st.button("Run rule-based smoothing"):
                    st.session_state.sch_smooth = smooth(tasks, res)
                sm = st.session_state.get("sch_smooth")
                if sm:
                    st.write(f"Overload before: **{sm['before']:.1f}** resource-days, after: **{sm['after']:.1f}**.")
                    if sm["delays"]:
                        st.dataframe(pd.DataFrame([{"Task": k, "Delay (days)": v} for k, v in sm["delays"].items()]), hide_index=True)
                        if st.button("Apply smoothing delays"):
                            st.session_state.sch_tasks = apply_delays(tasks, sm["delays"])
                            _reset_results()
                            st.session_state.sch_applied = "Smoothing delays applied. Click the check button again to confirm."
                            st.rerun()
                    if sm["after"] > 0:
                        st.info("Smoothing cannot remove all the overload within the available slack. Use **Resource leveling** (extend the timeline).")

            with t2:
                if st.button(f"Ask {ai.provider} how to smooth this out"):
                    if not ai.ready:
                        st.error(ai.missing_message())
                    else:
                        with st.spinner(f"Asking {ai.provider}..."):
                            try:
                                st.session_state.sch_ai = get_smoothing_recommendations(compute_slack(tasks), res, summary, ai.provider, ai.api_key, ai.model, ai.base_url)
                            except RuntimeError as exc:
                                st.error(str(exc))
                result = st.session_state.get("sch_ai")
                if result:
                    st.info(result.get("summary", ""))
                    if result.get("leveling_needed"):
                        st.warning("The AI says smoothing alone cannot resolve the conflicts: resource leveling (extending the timeline) is needed.")
                    recs = result.get("recommendations", [])
                    if recs:
                        st.dataframe(pd.DataFrame(recs).rename(columns={"task": "Task", "delay_days": "Recommended delay (days)", "rationale": "Rationale"}), hide_index=True)
                        delays = {r["task"]: int(r["delay_days"]) for r in recs if int(r.get("delay_days", 0)) > 0}
                        if delays and st.button("Apply the AI delays"):
                            st.session_state.sch_tasks = apply_delays(tasks, delays)
                            _reset_results()
                            st.session_state.sch_applied = "AI delays applied. Click the check button again to confirm."
                            st.rerun()

            with t3:
                st.write("Serial leveling: tasks may finish after their deadline and the project end date can move. Dependencies (finish-to-start) are respected.")
                if st.button("Run resource leveling"):
                    st.session_state.sch_level = level(tasks, res)
                lv = st.session_state.get("sch_level")
                if lv is not None:
                    new_finish = lv["Leveled Finish"].max()
                    extra = (new_finish - logic_finish).days
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Finish before leveling", logic_finish.strftime("%d %b %Y"))
                    k2.metric("Finish after leveling", new_finish.strftime("%d %b %Y"), f"+{extra} days", delta_color="inverse")
                    k3.metric("Tasks moved", int((lv["Delay (days)"] > 0).sum()))
                    show = lv[["Task", "Start Date", "Delay (days)", "Leveled Finish", "Deadline"]].copy()
                    show["Misses deadline"] = show["Leveled Finish"] > pd.to_datetime(show["Deadline"])
                    for col in ("Start Date", "Leveled Finish", "Deadline"):
                        show[col] = pd.to_datetime(show[col]).dt.date
                    st.dataframe(show, hide_index=True)
                    fig = px.timeline(lv.assign(Finish=lv["Leveled Finish"] + pd.Timedelta(days=1)), x_start="Start Date", x_end="Finish", y="Task", color="Delay (days)", color_continuous_scale="Blues")
                    fig.update_yaxes(autorange="reversed", title=None)
                    fig.update_layout(height=420, margin=dict(t=10, b=10, l=10, r=10))
                    st.plotly_chart(fig)
                    st.caption("With one person the leveled plan is the sequential plan: 24 working days against 21 by logic alone.")
                    if st.button("Apply the leveled schedule"):
                        st.session_state.sch_tasks = lv[data.tasks().columns.tolist()]
                        _reset_results()
                        st.session_state.sch_applied = "Leveled schedule applied. Click the check button again: no conflicts should remain."
                        st.rerun()

    if st.session_state.get("sch_applied"):
        st.success(st.session_state.sch_applied)
