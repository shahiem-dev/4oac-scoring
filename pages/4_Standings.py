"""Live standings — clubs, individuals, per-league. Drill into any club."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib import (DIVISIONS, load_anglers, load_catches_scored, load_comps,
                     render_season_sidebar, resolve_sub_team)

st.set_page_config(page_title="Standings · WCSAA League", page_icon="🏆", layout="wide")
active = render_season_sidebar()
st.title(f"🏆 Standings — {active}")

catches = load_catches_scored()
anglers = load_anglers()
comps = load_comps()

if catches.empty:
    st.info("No catches yet.")
    st.stop()

cc = resolve_sub_team(catches, anglers).merge(
    anglers.drop(columns=["sub_team"], errors="ignore"), on="wp_no", how="left")
cc["club"] = cc["club"].fillna("UNKNOWN").replace("", "UNKNOWN")
cc["sub_team"] = cc["sub_team"].fillna("").astype(str).str.upper().str.strip()
cc["Angler"] = (cc["first_name"].fillna("") + " " + cc["surname"].fillna("")).str.strip()
cc.loc[cc["Angler"] == "", "Angler"] = "(unknown)"
comp_order = sorted(catches["comp_id"].unique().tolist())
SUB_TEAMS = list("ABCDEFGHI")

tab_club, tab_ind, tab_league, tab_drill = st.tabs(
    ["By Club", "Individuals", "Per Division", "Club Drilldown"])

with tab_club:
    st.markdown("##### By Sub-team (A..I + A+B)")
    sub = cc.pivot_table(index="club", columns="sub_team",
                         values="points", aggfunc="sum")
    sub = sub.reindex(columns=SUB_TEAMS)
    out = pd.DataFrame(index=sub.index)
    out["PNTS A"] = sub["A"]; out["PNTS B"] = sub["B"]
    ab = sub["A"].fillna(0) + sub["B"].fillna(0)
    ab[sub["A"].isna() & sub["B"].isna()] = pd.NA
    out["PNTS A+B"] = ab
    for t in SUB_TEAMS[2:]:
        out[f"PNTS {t}"] = sub[t]
    out = out.sort_values("PNTS A+B", ascending=False, na_position="last").reset_index()
    out.insert(0, "Pos.", range(1, len(out) + 1))
    out = out.rename(columns={"club": "CLUB"})
    st.dataframe(out, use_container_width=True, hide_index=True)
    st.download_button("⬇ Download CSV", out.to_csv(index=False).encode(),
                       "club_subteam_standings.csv", "text/csv")

    st.markdown("##### Per-comp Totals")
    pivot = cc.pivot_table(index="club", columns="comp_id", values="points",
                           aggfunc="sum", fill_value=0)
    pivot = pivot.reindex(columns=comp_order, fill_value=0)
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("Total", ascending=False).reset_index()
    pivot.insert(0, "Pos.", range(1, len(pivot) + 1))
    pivot = pivot.rename(columns={"club": "Club"})
    st.dataframe(pivot, use_container_width=True, hide_index=True)
    st.download_button("⬇ Download CSV", pivot.to_csv(index=False).encode(),
                       "club_per_comp_standings.csv", "text/csv")

with tab_ind:
    pivot = cc.pivot_table(index=["wp_no", "Angler", "club", "league_code"],
                           columns="comp_id", values="points",
                           aggfunc="sum", fill_value=0).reset_index()
    for c in comp_order:
        if c not in pivot.columns: pivot[c] = 0
    pivot["Total"] = pivot[comp_order].sum(axis=1) if comp_order else 0
    pivot = pivot.sort_values("Total", ascending=False).reset_index(drop=True)
    pivot.insert(0, "Rank", range(1, len(pivot) + 1))
    pivot = pivot.rename(columns={"wp_no": "WP No", "club": "Club", "league_code": "Lg"})
    cols = ["Rank", "WP No", "Angler", "Club", "Lg"] + comp_order + ["Total"]
    st.dataframe(pivot[cols], use_container_width=True, hide_index=True)
    st.download_button("⬇ Download CSV", pivot[cols].to_csv(index=False).encode(),
                       "individual_standings.csv", "text/csv")

with tab_league:
    leagues = sorted([x for x in cc["league_code"].dropna().unique() if x != ""])
    if not leagues:
        st.info("No divisions set on anglers — set them on the **Clubs** page.")
    for lg in leagues:
        st.markdown(f"### {lg} — {DIVISIONS.get(lg.upper(), '')}")
        sub = cc[cc["league_code"] == lg]
        p = sub.pivot_table(index=["wp_no", "Angler", "club"],
                            columns="comp_id", values="points",
                            aggfunc="sum", fill_value=0).reset_index()
        for c in comp_order:
            if c not in p.columns: p[c] = 0
        p["Total"] = p[comp_order].sum(axis=1) if comp_order else 0
        p = p.sort_values("Total", ascending=False).reset_index(drop=True)
        p.insert(0, "Rank", range(1, len(p) + 1))
        p = p.rename(columns={"wp_no": "WP No", "club": "Club"})
        st.dataframe(p, use_container_width=True, hide_index=True)

with tab_drill:
    clubs = sorted(cc["club"].unique().tolist())
    club = st.selectbox("Pick a club", clubs)
    sub = cc[cc["club"] == club]
    p = sub.pivot_table(index=["wp_no", "Angler", "league_code"],
                        columns="comp_id", values="points",
                        aggfunc="sum", fill_value=0).reset_index()
    for c in comp_order:
        if c not in p.columns: p[c] = 0
    p["Total"] = p[comp_order].sum(axis=1) if comp_order else 0
    p = p.sort_values("Total", ascending=False).reset_index(drop=True)
    p.insert(0, "Rank", range(1, len(p) + 1))
    p = p.rename(columns={"wp_no": "WP No", "league_code": "Lg"})
    st.markdown(f"#### {club} — Members")
    st.dataframe(p, use_container_width=True, hide_index=True)

    st.markdown(f"#### {club} — Catch Detail")
    detail = sub[["comp_id", "wp_no", "Angler", "species_raw", "length_cm",
                  "weight_kg", "edible", "points", "status"]] \
        .rename(columns={"comp_id": "Comp", "wp_no": "WP No",
                         "species_raw": "Species", "length_cm": "Length",
                         "weight_kg": "Weight", "edible": "Ed",
                         "points": "Pts", "status": "Status"})
    st.dataframe(detail.sort_values(["Comp", "WP No"]),
                 use_container_width=True, hide_index=True)
