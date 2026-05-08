"""Catch-based leaderboards — heaviest fish, most fish, per club / angler."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib import (DIVISIONS, apply_filters, load_anglers,
                     load_catches_scored, load_comps, render_global_filters,
                     render_season_sidebar)
from ui import divider_label, empty_state, leader_banner, page_header, section_label

st.set_page_config(page_title="Leaderboards · WCSAA League",
                   page_icon="📋", layout="wide")
active = render_season_sidebar()
page_header("Leaderboards",
            "Catch records — heaviest fish, most fish per angler & club",
            "📋", active)

catches = load_catches_scored()
anglers = load_anglers()
comps   = load_comps()

if catches.empty:
    empty_state("No catches yet — record some on the Catches page.", "🎣")
    st.stop()

filters = render_global_filters(catches, anglers)
catches, anglers = apply_filters(catches, anglers, filters)
if catches.empty:
    st.warning("No catches match the current filters.")
    st.stop()

# ── Enrich ────────────────────────────────────────────────────────────────
cc = catches.merge(
    anglers[["wp_no", "first_name", "surname", "club", "league_code"]],
    on="wp_no", how="left")
cc["club"]        = cc["club"].fillna("UNKNOWN").replace("", "UNKNOWN")
cc["league_code"] = cc["league_code"].fillna("").astype(str).str.upper().str.strip()
cc["Angler"]      = (cc["first_name"].fillna("") + " "
                     + cc["surname"].fillna("")).str.strip()
cc.loc[cc["Angler"] == "", "Angler"] = "(unknown)"
cc["weight_kg"]   = pd.to_numeric(cc["weight_kg"], errors="coerce").fillna(0.0)
cc["edible"]      = cc["edible"].fillna("").astype(str).str.upper()
cc["valid"]       = cc["status"].fillna("").astype(str).str.startswith("ok")

st.caption(f"Showing **{len(cc)}** catches · use sidebar filters to narrow.")

# ── Heaviest catches ──────────────────────────────────────────────────────
divider_label("Heaviest catches")
edible_valid     = cc[(cc["edible"] == "Y") & cc["valid"] & (cc["weight_kg"] > 0)]
non_edible_valid = cc[(cc["edible"] == "N") & cc["valid"] & (cc["weight_kg"] > 0)]

col_e, col_n = st.columns(2)

with col_e:
    with st.container(border=True):
        section_label("Heaviest edible")
        if edible_valid.empty:
            empty_state("No edible catches yet.", "🐟")
        else:
            top_e = (edible_valid.sort_values("weight_kg", ascending=False)
                     .head(10)[["comp_id", "Angler", "club", "canonical_species",
                                "length_cm", "weight_kg", "points"]]
                     .rename(columns={"comp_id": "Comp", "club": "Club",
                                      "canonical_species": "Species",
                                      "length_cm": "Length",
                                      "weight_kg": "Weight (kg)", "points": "Pts"}))
            top_e.insert(0, "Pos.", range(1, len(top_e) + 1))
            st.dataframe(top_e, use_container_width=True, hide_index=True)
            w = top_e.iloc[0]
            leader_banner("🥇", w["Angler"],
                          detail=f"{w['Species']} · {w['Comp']}",
                          pts=f"{w['Weight (kg)']:.2f} kg")

with col_n:
    with st.container(border=True):
        section_label("Heaviest non-edible")
        if non_edible_valid.empty:
            empty_state("No non-edible catches yet.", "🦈")
        else:
            top_n = (non_edible_valid.sort_values("weight_kg", ascending=False)
                     .head(10)[["comp_id", "Angler", "club", "canonical_species",
                                "length_cm", "weight_kg", "points"]]
                     .rename(columns={"comp_id": "Comp", "club": "Club",
                                      "canonical_species": "Species",
                                      "length_cm": "Length",
                                      "weight_kg": "Weight (kg)", "points": "Pts"}))
            top_n.insert(0, "Pos.", range(1, len(top_n) + 1))
            st.dataframe(top_n, use_container_width=True, hide_index=True)
            w = top_n.iloc[0]
            leader_banner("🥇", w["Angler"],
                          detail=f"{w['Species']} · {w['Comp']}",
                          pts=f"{w['Weight (kg)']:.2f} kg")

# ── Catches per club ──────────────────────────────────────────────────────
divider_label("Catches per club")
counted = cc[cc["valid"]].copy()
col3, col4 = st.columns(2)

with col3:
    with st.container(border=True):
        section_label("Most edibles per club")
        e_per_club = (counted[counted["edible"] == "Y"]
                      .groupby("club").size()
                      .reset_index(name="Edible catches")
                      .sort_values("Edible catches", ascending=False)
                      .reset_index(drop=True))
        if e_per_club.empty:
            empty_state("No edible catches yet.", "🐟")
        else:
            e_per_club.insert(0, "Pos.", range(1, len(e_per_club) + 1))
            e_per_club = e_per_club.rename(columns={"club": "Club"})
            st.dataframe(e_per_club, use_container_width=True, hide_index=True)
            w = e_per_club.iloc[0]
            leader_banner("🎖", w["Club"],
                          detail="Radio Good Hope Trophy leader",
                          pts=f"{w['Edible catches']} catches")

with col4:
    with st.container(border=True):
        section_label("Most non-edibles per club")
        n_per_club = (counted[counted["edible"] == "N"]
                      .groupby("club").size()
                      .reset_index(name="Non-edible catches")
                      .sort_values("Non-edible catches", ascending=False)
                      .reset_index(drop=True))
        if n_per_club.empty:
            empty_state("No non-edible catches yet.", "🦈")
        else:
            n_per_club.insert(0, "Pos.", range(1, len(n_per_club) + 1))
            n_per_club = n_per_club.rename(columns={"club": "Club"})
            st.dataframe(n_per_club, use_container_width=True, hide_index=True)
            if not n_per_club.empty:
                w = n_per_club.iloc[0]
                leader_banner("🎖", w["Club"],
                              pts=f"{w['Non-edible catches']} catches")

# ── Most fish per angler ──────────────────────────────────────────────────
divider_label("Most fish per angler (top 25)")
per_angler = (counted.groupby(["wp_no", "Angler", "club", "league_code"])
              .agg(catches=("comp_id", "count"),
                   total_weight=("weight_kg", "sum"),
                   total_points=("points", "sum"))
              .reset_index()
              .sort_values(["catches", "total_weight"], ascending=[False, False])
              .head(25).reset_index(drop=True))
per_angler.insert(0, "Pos.", range(1, len(per_angler) + 1))
per_angler["total_weight"]  = per_angler["total_weight"].round(2)
per_angler["total_points"]  = per_angler["total_points"].round(2)
per_angler = per_angler.rename(columns={
    "wp_no": "WP No", "club": "Club", "league_code": "Lg",
    "catches": "Catches", "total_weight": "Total Weight (kg)",
    "total_points": "Total Pts"})
st.dataframe(per_angler, use_container_width=True, hide_index=True)
if not per_angler.empty:
    w = per_angler.iloc[0]
    leader_banner("🎣", w["Angler"], detail=w["Club"],
                  pts=f"{w['Catches']} catches · {w['Total Pts']:.2f} pts")
