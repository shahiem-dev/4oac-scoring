"""Trophies page — all WCSAA trophies in one view.

Logic lives in trophies.py; this page is mostly layout + section banners.
"""
from __future__ import annotations

import streamlit as st

from app_lib import (load_anglers, load_catches_scored, load_comps,
                     load_team_assignments, load_trophy_nominees,
                     render_season_sidebar)
from standings import BEST_N_DEFAULT
from trophies import (blue_ray, champion_division, first_comp_in_month,
                      lowest_comp_id, masters_four, mario_texeira, nj_van_as,
                      piet_alberts, radio_good_hope, sir_drummond_chapman,
                      station_motors, wallace_van_wyk)

st.set_page_config(page_title="Trophies · WCSAA League",
                   page_icon="🏆", layout="wide")
active = render_season_sidebar()
st.title(f"🏆 Trophies — {active}")
st.caption("All trophy rankings derived from current scored catches. "
           "Top row in each table is the leader.")

catches = load_catches_scored()
anglers = load_anglers()
comps = load_comps()
team_assignments = load_team_assignments()
nominees = load_trophy_nominees()

if catches.empty:
    st.info("No catches yet — trophies will populate as catches are recorded.")
    st.stop()

comp_order = sorted(catches["comp_id"].unique().tolist())
jan_comp = first_comp_in_month(comps, 1)
feb_comp = first_comp_in_month(comps, 2)
first_comp = lowest_comp_id(comps)


def _show(df, leader_msg=None):
    if df is None or len(df) == 0:
        st.info("No data yet for this trophy.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    if leader_msg and len(df):
        st.success(leader_msg)


# ---- Tabs --------------------------------------------------------------
tab_team, tab_individual, tab_catch = st.tabs(
    ["🛡 Team Trophies", "👤 Individual Trophies", "🐟 Catch Trophies"])

# ---- Team trophies -----------------------------------------------------
with tab_team:
    st.subheader("Masters-Four Trophy")
    st.caption("Top 4 Masters per club per competition, summed across all comps.")
    df = masters_four(catches, anglers)
    if not df.empty:
        win = df.iloc[0]
        _show(df, f"🥇 **{win['Club']}** — {win['Total']:.2f} pts")
    else:
        _show(df)

    st.divider()
    st.subheader("Sir Drummond Chapman Trophy")
    if not jan_comp:
        st.warning("No comp dated in January — set comp dates on the Competitions page.")
    else:
        st.caption(f"4 nominees per club in **{jan_comp}** (first January comp). "
                   "Set nominees on Competitions → Trophy Nominees tab.")
        df, _ = sir_drummond_chapman(catches, anglers, nominees,
                                      jan_comp_id=jan_comp)
        if df.empty:
            st.info("No SDC nominees set yet, or no catches in the January comp.")
        else:
            win = df.iloc[0]
            _show(df, f"🥇 **{win['Club']}** — {win['Team Points']:.2f} pts")

    st.divider()
    st.subheader("Wallace van Wyk Trophy")
    if not feb_comp:
        st.warning("No comp dated in February — set comp dates on the Competitions page.")
    else:
        st.caption(f"Team A (8 anglers per club) in **{feb_comp}** (first February comp).")
        df, _ = wallace_van_wyk(catches, anglers, team_assignments,
                                 feb_comp_id=feb_comp)
        if df.empty:
            st.info("No Team A assigned for the February comp, or no catches yet.")
        else:
            win = df.iloc[0]
            _show(df, f"🥇 **{win['Club']}** — {win['Team Points']:.2f} pts")

    st.divider()
    st.subheader("Radio Good Hope Trophy")
    st.caption("Club with the most edible fish caught.")
    df = radio_good_hope(catches, anglers)
    if not df.empty:
        win = df.iloc[0]
        _show(df, f"🥇 **{win['Club']}** — {win['Edible catches']} edible(s)")
    else:
        _show(df)

# ---- Individual trophies ----------------------------------------------
with tab_individual:
    n = BEST_N_DEFAULT

    st.subheader("N.J. van As — Overall Champion")
    st.caption(f"Highest total points across all divisions (best {n} of {len(comp_order)}).")
    df = nj_van_as(catches, anglers, comp_order=comp_order, n=n)
    if not df.empty:
        win = df.iloc[0]
        _show(df.head(20),
              f"🥇 **{win['Angler']}** ({win['Club']}, {win['Lg']}) — "
              f"{win['Total']:.2f} pts")
    else:
        _show(df)

    st.divider()
    st.subheader("Mutual Trophy — Champion Junior")
    st.caption(f"Top Junior or Kids angler (J+K) by total points (best {n} of {len(comp_order)}).")
    df = champion_division(catches, anglers, "J", "K",
                            comp_order=comp_order, n=n)
    if not df.empty:
        win = df.iloc[0]
        _show(df.head(15),
              f"🥇 **{win['Angler']}** ({win['Club']}, {win['Lg']}) — {win['Total']:.2f} pts")
    else:
        _show(df)

    st.divider()
    st.subheader("Syfie Douglas Trophy — Champion Lady")
    df = champion_division(catches, anglers, "L",
                            comp_order=comp_order, n=n)
    if not df.empty:
        win = df.iloc[0]
        _show(df.head(15),
              f"🥇 **{win['Angler']}** ({win['Club']}) — {win['Total']:.2f} pts")
    else:
        _show(df)

    st.divider()
    st.subheader("Willie Morries Trophy — Champion Master")
    df = champion_division(catches, anglers, "M",
                            comp_order=comp_order, n=n)
    if not df.empty:
        win = df.iloc[0]
        _show(df.head(15),
              f"🥇 **{win['Angler']}** ({win['Club']}) — {win['Total']:.2f} pts")
    else:
        _show(df)

    st.divider()
    st.subheader("Piet Alberts Trophy — Junior Winner of First Comp")
    if not first_comp:
        st.warning("No competitions yet.")
    else:
        st.caption(f"Junior or Kids winner of **{first_comp}** (lowest comp_id).")
        df = piet_alberts(catches, anglers, first_comp)
        if not df.empty:
            win = df.iloc[0]
            _show(df, f"🥇 **{win['Angler']}** ({win['Club']}, {win['Lg']}) — "
                       f"{win['Points']:.2f} pts")
        else:
            _show(df)

    st.divider()
    st.subheader("Blue Ray Trophy — Most Consistent Angler")
    st.caption(f"Drop the worst rank, average the remaining {n} ranks. "
               "Lower average = more consistent.")
    df = blue_ray(catches, anglers, comp_order=comp_order, n=n)
    if not df.empty:
        win = df.iloc[0]
        _show(df.head(20),
              f"🥇 **{win['Angler']}** ({win['Club']}) — avg rank {win['Avg']:.2f} "
              f"(dropped {win['Dropped']})")
    else:
        _show(df)

# ---- Catch trophies ---------------------------------------------------
with tab_catch:
    st.subheader("Mario Texeira Trophy — Heaviest Edible")
    df = mario_texeira(catches, anglers)
    if not df.empty:
        win = df.iloc[0]
        _show(df, f"🥇 **{win['Angler']}** ({win['Club']}) — "
                   f"{win['Species']} @ {win['Weight (kg)']:.2f} kg in {win['Comp']}")
    else:
        _show(df)

    st.divider()
    st.subheader("Station Motors Trophy — Heaviest Non-Edible")
    df = station_motors(catches, anglers)
    if not df.empty:
        win = df.iloc[0]
        _show(df, f"🥇 **{win['Angler']}** ({win['Club']}) — "
                   f"{win['Species']} @ {win['Weight (kg)']:.2f} kg in {win['Comp']}")
    else:
        _show(df)
