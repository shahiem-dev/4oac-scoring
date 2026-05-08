"""All WCSAA trophies — live rankings derived from scored catches."""
from __future__ import annotations

import streamlit as st

from app_lib import (apply_filters, highlight_leader, load_anglers,
                     load_catches_scored, load_comps, load_team_assignments,
                     load_trophy_nominees, render_global_filters,
                     render_season_sidebar)
from standings import BEST_N_DEFAULT
from trophies import (blue_ray, champion_division, first_comp_in_month,
                      lowest_comp_id, mario_texeira, masters_four, nj_van_as,
                      piet_alberts, radio_good_hope, sir_drummond_chapman,
                      station_motors, wallace_van_wyk)
from ui import divider_label, empty_state, leader_banner, page_header, section_label

st.set_page_config(page_title="Trophies · WCSAA League",
                   page_icon="🏆", layout="wide")
active = render_season_sidebar()
page_header("Trophies",
            "All WCSAA trophies — rankings updated live from scored catches",
            "🏆", active)

catches          = load_catches_scored()
anglers          = load_anglers()
comps            = load_comps()
team_assignments = load_team_assignments()
nominees         = load_trophy_nominees()

if catches.empty:
    empty_state("No catches yet — trophies will populate as catches are recorded.", "🏆")
    st.stop()

filters = render_global_filters(catches, anglers)
catches, anglers = apply_filters(catches, anglers, filters)
if catches.empty:
    st.warning("No catches match the current filters.")
    st.stop()

comp_order  = sorted(catches["comp_id"].unique().tolist())
jan_comp    = first_comp_in_month(comps, 1)
feb_comp    = first_comp_in_month(comps, 2)
first_comp  = lowest_comp_id(comps)
n           = BEST_N_DEFAULT


def _show(df, medal: str = "🥇", name_col: str | None = None,
          detail_col: str | None = None, pts_col: str | None = None,
          empty_msg: str = "No data yet for this trophy.") -> None:
    """Render a trophy table + leader banner."""
    if df is None or df.empty:
        empty_state(empty_msg, "🏆")
        return
    st.dataframe(highlight_leader(df), use_container_width=True, hide_index=True)
    if name_col and name_col in df.columns:
        row    = df.iloc[0]
        name   = str(row[name_col])
        detail = str(row[detail_col]) if detail_col and detail_col in df.columns else ""
        pts    = str(row[pts_col])    if pts_col   and pts_col   in df.columns else ""
        leader_banner(medal, name, detail=detail, pts=pts)


# ── Tabs ──────────────────────────────────────────────────────────────────
tab_team, tab_ind, tab_catch = st.tabs(
    ["🛡  Team Trophies", "👤  Individual Trophies", "🐟  Catch Trophies"])

# ── Team trophies ─────────────────────────────────────────────────────────
with tab_team:

    with st.container(border=True):
        section_label("Masters-Four Trophy")
        st.caption("Top 4 Masters per club per competition, summed across all comps.")
        df = masters_four(catches, anglers)
        _show(df, name_col="Club",
              pts_col="Total" if not df.empty and "Total" in df.columns else None)

    divider_label("")

    with st.container(border=True):
        section_label("Sir Drummond Chapman Trophy")
        if not jan_comp:
            st.warning("No competition dated in January — set dates on the Competitions page.")
        else:
            st.caption(
                f"4 nominees per club in **{jan_comp}** (first January comp). "
                "Set nominees on Competitions → SDC Nominees tab.")
            df, _ = sir_drummond_chapman(catches, anglers, nominees,
                                          jan_comp_id=jan_comp)
            if df.empty:
                empty_state("No SDC nominees set yet, or no catches in the January comp.", "🏆")
            else:
                _show(df, name_col="Club",
                      pts_col="Team Points" if "Team Points" in df.columns else None)

    divider_label("")

    with st.container(border=True):
        section_label("Wallace van Wyk Trophy")
        if not feb_comp:
            st.warning("No competition dated in February — set dates on the Competitions page.")
        else:
            st.caption(f"Team A (8 anglers per club) in **{feb_comp}** (first February comp).")
            df, _ = wallace_van_wyk(catches, anglers, team_assignments,
                                     feb_comp_id=feb_comp)
            if df.empty:
                empty_state("No Team A assigned for the February comp, or no catches yet.", "🏆")
            else:
                _show(df, name_col="Club",
                      pts_col="Team Points" if "Team Points" in df.columns else None)

    divider_label("")

    with st.container(border=True):
        section_label("Radio Good Hope Trophy")
        st.caption("Club with the most edible fish caught across the season.")
        df = radio_good_hope(catches, anglers)
        _show(df, name_col="Club",
              pts_col="Edible catches" if not df.empty and "Edible catches" in df.columns else None)

# ── Individual trophies ───────────────────────────────────────────────────
with tab_ind:

    with st.container(border=True):
        section_label("N.J. van As — Overall Champion")
        st.caption(f"Highest total points across all divisions (best {n} of {len(comp_order)}).")
        df = nj_van_as(catches, anglers, comp_order=comp_order, n=n)
        _show(df.head(20), name_col="Angler",
              detail_col="Club" if not df.empty and "Club" in df.columns else None,
              pts_col="Total"   if not df.empty and "Total" in df.columns else None)

    divider_label("")

    with st.container(border=True):
        section_label("Mutual Trophy — Champion Junior")
        st.caption(f"Top Junior/Kids angler (J+K) by total points (best {n} of {len(comp_order)}).")
        df = champion_division(catches, anglers, "J", "K",
                                comp_order=comp_order, n=n)
        _show(df.head(15), name_col="Angler",
              detail_col="Club"  if not df.empty and "Club"  in df.columns else None,
              pts_col="Total"    if not df.empty and "Total" in df.columns else None)

    divider_label("")

    with st.container(border=True):
        section_label("Syfie Douglas Trophy — Champion Lady")
        df = champion_division(catches, anglers, "L",
                                comp_order=comp_order, n=n)
        _show(df.head(15), name_col="Angler",
              detail_col="Club"  if not df.empty and "Club"  in df.columns else None,
              pts_col="Total"    if not df.empty and "Total" in df.columns else None)

    divider_label("")

    with st.container(border=True):
        section_label("Willie Morries Trophy — Champion Master")
        df = champion_division(catches, anglers, "M",
                                comp_order=comp_order, n=n)
        _show(df.head(15), name_col="Angler",
              detail_col="Club"  if not df.empty and "Club"  in df.columns else None,
              pts_col="Total"    if not df.empty and "Total" in df.columns else None)

    divider_label("")

    with st.container(border=True):
        section_label("Piet Alberts Trophy — Junior Winner of First Comp")
        if not first_comp:
            st.warning("No competitions yet.")
        else:
            st.caption(f"Junior or Kids winner of **{first_comp}** (lowest comp_id).")
            df = piet_alberts(catches, anglers, first_comp)
            _show(df, name_col="Angler",
                  detail_col="Club"   if not df.empty and "Club"   in df.columns else None,
                  pts_col="Points"    if not df.empty and "Points" in df.columns else None)

    divider_label("")

    with st.container(border=True):
        section_label("Blue Ray Trophy — Most Consistent Angler")
        st.caption(
            f"Drop the worst rank, average the remaining {n} ranks. "
            "Lower average = more consistent.")
        df = blue_ray(catches, anglers, comp_order=comp_order, n=n)
        _show(df.head(20), name_col="Angler",
              detail_col="Club" if not df.empty and "Club" in df.columns else None,
              pts_col="Avg"     if not df.empty and "Avg"  in df.columns else None)

# ── Catch trophies ────────────────────────────────────────────────────────
with tab_catch:

    with st.container(border=True):
        section_label("Mario Texeira Trophy — Heaviest Edible")
        df = mario_texeira(catches, anglers)
        _show(df, name_col="Angler",
              detail_col="Club"       if not df.empty and "Club"       in df.columns else None,
              pts_col="Weight (kg)"   if not df.empty and "Weight (kg)" in df.columns else None)

    divider_label("")

    with st.container(border=True):
        section_label("Station Motors Trophy — Heaviest Non-Edible")
        df = station_motors(catches, anglers)
        _show(df, name_col="Angler",
              detail_col="Club"       if not df.empty and "Club"       in df.columns else None,
              pts_col="Weight (kg)"   if not df.empty and "Weight (kg)" in df.columns else None)
