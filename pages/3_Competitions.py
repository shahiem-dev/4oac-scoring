"""Manage competitions and per-competition team assignments (A–I)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib import (CLUBS, SUB_TEAMS, comp_options, load_anglers, load_comps,
                     load_team_assignments, render_season_sidebar, save_comps,
                     save_team_assignments)

st.set_page_config(page_title="Competitions · WCSAA League", page_icon="📅", layout="wide")
active = render_season_sidebar()
st.title(f"📅 Competitions — {active}")

tab_sched, tab_teams = st.tabs(["📋 Schedule", "👥 Team Selection (per comp)"])

# ---- Schedule -----------------------------------------------------------
with tab_sched:
    st.caption("One row per competition. comp_id e.g. 'IC 8'.")
    df = load_comps()
    edited = st.data_editor(
        df, num_rows="dynamic", use_container_width=True,
        column_config={
            "comp_id": st.column_config.TextColumn("Comp ID", required=True),
            "date": st.column_config.TextColumn("Date (YYYY-MM-DD)"),
            "venue": st.column_config.TextColumn("Venue"),
        },
        key="comp_editor",
    )
    if st.button("💾 Save schedule", type="primary"):
        save_comps(edited)
        st.success(f"Saved {len(edited)} competitions.")
        st.rerun()

# ---- Team Selection -----------------------------------------------------
with tab_teams:
    st.caption("Teams A–I are picked **fresh per competition**. Past comps keep their assignments — "
               "changing a future comp's teams won't affect already-recorded points.")
    comps = comp_options()
    if not comps:
        st.info("Add at least one competition on the **Schedule** tab first.")
        st.stop()

    comp = st.selectbox("Competition", comps, index=len(comps) - 1, key="team_sel_comp")
    anglers = load_anglers()
    if anglers.empty:
        st.info("No anglers yet — add them on the **Clubs** page first.")
        st.stop()

    ta_all = load_team_assignments()
    ta_comp = ta_all[ta_all["comp_id"] == comp].copy()

    club_filter = st.multiselect("Filter clubs", CLUBS, default=[])
    view = anglers.copy()
    if club_filter:
        view = view[view["club"].isin(club_filter)]
    view["Angler"] = view["first_name"].fillna("") + " " + view["surname"].fillna("")
    view = view.merge(ta_comp[["wp_no", "sub_team"]].rename(columns={"sub_team": "team"}),
                      on="wp_no", how="left")
    view["team"] = view["team"].fillna("")
    view = view[["wp_no", "Angler", "club", "team"]].sort_values(["club", "Angler"]).reset_index(drop=True)

    # Per-team count summary
    counts = view[view["team"] != ""].groupby("team").size().reindex(SUB_TEAMS, fill_value=0)
    st.markdown("**Team sizes for this comp**")
    cs = st.columns(len(SUB_TEAMS))
    for i, t in enumerate(SUB_TEAMS):
        cs[i].metric(f"Team {t}", int(counts[t]))

    edited = st.data_editor(
        view, use_container_width=True, hide_index=True, key=f"team_edit_{comp}",
        column_config={
            "wp_no": st.column_config.TextColumn("WP No", disabled=True),
            "Angler": st.column_config.TextColumn("Angler", disabled=True),
            "club": st.column_config.TextColumn("Club", disabled=True),
            "team": st.column_config.SelectboxColumn(
                "Team (A–I)", options=[""] + SUB_TEAMS,
                help="Blank = not selected for this comp"),
        },
    )

    c1, c2, c3 = st.columns([1, 1, 4])
    if c1.button("💾 Save team selection", type="primary"):
        new_rows = edited[edited["team"] != ""][["wp_no", "team"]].copy()
        new_rows["comp_id"] = comp
        new_rows = new_rows.rename(columns={"team": "sub_team"})
        # Replace this comp's rows; keep other comps untouched
        keep_other = ta_all[ta_all["comp_id"] != comp]
        save_team_assignments(pd.concat([keep_other, new_rows], ignore_index=True))
        st.success(f"Saved team selection for {comp} ({len(new_rows)} anglers).")
        st.rerun()

    if c2.button("🗑 Clear teams for this comp"):
        keep_other = ta_all[ta_all["comp_id"] != comp]
        save_team_assignments(keep_other)
        st.success(f"Cleared all team assignments for {comp}.")
        st.rerun()
