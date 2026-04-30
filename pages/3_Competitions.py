"""Manage competitions and per-competition team assignments (A–I)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib import (CLUBS, SUB_TEAMS, comp_options, load_anglers, load_comps,
                     load_team_assignments, load_trophy_nominees,
                     render_season_sidebar, save_comps,
                     save_team_assignments, save_trophy_nominees)
from trophies import first_comp_in_month

st.set_page_config(page_title="Competitions · WCSAA League", page_icon="📅", layout="wide")
active = render_season_sidebar()
st.title(f"📅 Competitions — {active}")

tab_sched, tab_teams, tab_nom = st.tabs(
    ["📋 Schedule", "👥 Team Selection (per comp)",
     "🏅 Trophy Nominees (Sir Drummond Chapman)"])

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

    TEAM_LIMIT = 8
    edited = st.data_editor(
        view, use_container_width=True, hide_index=True, key=f"team_edit_{comp}",
        column_config={
            "wp_no": st.column_config.TextColumn("WP No", disabled=True),
            "Angler": st.column_config.TextColumn("Angler", disabled=True),
            "club": st.column_config.TextColumn("Club", disabled=True),
            "team": st.column_config.SelectboxColumn(
                "Team (A–I)", options=[""] + SUB_TEAMS,
                help=f"Blank = not selected. Max {TEAM_LIMIT} anglers per team."),
        },
    )

    counts = edited[edited["team"] != ""].groupby("team").size().reindex(SUB_TEAMS, fill_value=0)
    over = [t for t in SUB_TEAMS if counts[t] > TEAM_LIMIT]
    st.markdown(f"**Team sizes for this comp** (max {TEAM_LIMIT} per team)")
    cs = st.columns(len(SUB_TEAMS))
    for i, t in enumerate(SUB_TEAMS):
        n = int(counts[t])
        delta = f"+{n - TEAM_LIMIT} over" if n > TEAM_LIMIT else None
        cs[i].metric(f"Team {t}", n, delta=delta, delta_color="inverse" if delta else "off")

    if over:
        st.error(f"Team(s) {', '.join(over)} exceed the {TEAM_LIMIT}-angler limit. "
                 "Reduce them before saving.")

    c1, c2, c3 = st.columns([1, 1, 4])
    if c1.button("💾 Save team selection", type="primary", disabled=bool(over)):
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

# ---- Sir Drummond Chapman nominees -------------------------------------
with tab_nom:
    st.caption("**Sir Drummond Chapman Trophy** — each club nominates **4 anglers** "
               "to compete in the **first January competition**. Only their points "
               "in that comp count toward the trophy.")
    comps_df = load_comps()
    jan_comp = first_comp_in_month(comps_df, 1)
    if not jan_comp:
        st.warning("No competition with a date in January found. Add the comp date "
                   "in the Schedule tab first (format YYYY-MM-DD).")
    else:
        st.info(f"Target comp: **{jan_comp}**")
        anglers = load_anglers()
        if anglers.empty:
            st.info("No anglers yet — add them on the **Clubs** page.")
        else:
            nom_all = load_trophy_nominees()
            sdc = nom_all[(nom_all["trophy"] == "SDC") &
                          (nom_all["comp_id"] == jan_comp)]
            club_pick = st.selectbox("Club", CLUBS, key="sdc_club")
            club_anglers = anglers[anglers["club"] == club_pick].copy()
            if club_anglers.empty:
                st.info(f"No anglers in {club_pick} yet.")
            else:
                club_anglers["Angler"] = (club_anglers["first_name"].fillna("") + " "
                                           + club_anglers["surname"].fillna("")).str.strip()
                already = sdc[sdc["club"] == club_pick]["wp_no"].tolist()
                club_anglers["nominee"] = club_anglers["wp_no"].isin(already)
                view = club_anglers[["wp_no", "Angler", "league_code", "nominee"]] \
                    .sort_values("Angler").reset_index(drop=True)
                edited = st.data_editor(
                    view, hide_index=True, use_container_width=True,
                    key=f"sdc_edit_{club_pick}",
                    column_config={
                        "wp_no": st.column_config.TextColumn("WP No", disabled=True),
                        "Angler": st.column_config.TextColumn("Angler", disabled=True),
                        "league_code": st.column_config.TextColumn("Lg", disabled=True),
                        "nominee": st.column_config.CheckboxColumn(
                            "Nominee (max 4)", help="Tick exactly 4 per club"),
                    },
                )
                picked = edited[edited["nominee"]]
                n_picked = len(picked)
                if n_picked > 4:
                    st.error(f"Selected {n_picked} — must be 4 or fewer.")
                else:
                    st.caption(f"Selected: **{n_picked}** of 4")

                if st.button("💾 Save nominees for this club",
                             type="primary", disabled=(n_picked > 4),
                             key=f"sdc_save_{club_pick}"):
                    keep = nom_all[~((nom_all["trophy"] == "SDC") &
                                     (nom_all["comp_id"] == jan_comp) &
                                     (nom_all["club"] == club_pick))]
                    new_rows = picked[["wp_no"]].assign(
                        trophy="SDC", comp_id=jan_comp, club=club_pick)
                    save_trophy_nominees(pd.concat([keep, new_rows], ignore_index=True))
                    st.success(f"Saved {n_picked} SDC nominee(s) for {club_pick}.")
                    st.rerun()

            st.divider()
            st.markdown("**All current SDC nominees**")
            if sdc.empty:
                st.info("No nominees set yet.")
            else:
                pretty = sdc.merge(
                    anglers.assign(Angler=lambda d: (d["first_name"].fillna("") + " "
                                                      + d["surname"].fillna("")).str.strip())[
                        ["wp_no", "Angler"]],
                    on="wp_no", how="left")
                pretty = pretty[["club", "wp_no", "Angler"]].rename(
                    columns={"club": "Club", "wp_no": "WP No"})
                st.dataframe(pretty.sort_values(["Club", "Angler"]),
                             use_container_width=True, hide_index=True)
