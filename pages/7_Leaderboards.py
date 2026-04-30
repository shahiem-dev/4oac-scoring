"""Catch-based leaderboards — heaviest fish, most fish, per club / angler.

Distinct from the points-based standings (Page 4). These are CATCH metrics:
weight records and counts, not season points totals.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib import (DIVISIONS, apply_filters, load_anglers,
                     load_catches_scored, load_comps, render_global_filters,
                     render_season_sidebar)

st.set_page_config(page_title="Leaderboards · WCSAA League",
                   page_icon="📋", layout="wide")
active = render_season_sidebar()
st.title(f"📋 Leaderboards — {active}")
st.caption("Catch-based records: heaviest fish, most fish per angler / club. "
           "Distinct from points standings on the Standings page.")

catches = load_catches_scored()
anglers = load_anglers()
comps = load_comps()

if catches.empty:
    st.info("No catches yet.")
    st.stop()

filters = render_global_filters(catches, anglers)
catches, anglers = apply_filters(catches, anglers, filters)
if catches.empty:
    st.warning("No catches match the current filters.")
    st.stop()

# ---- Enrich with angler + club + division ------------------------------
cc = catches.merge(
    anglers[["wp_no", "first_name", "surname", "club", "league_code"]],
    on="wp_no", how="left",
)
cc["club"] = cc["club"].fillna("UNKNOWN").replace("", "UNKNOWN")
cc["league_code"] = cc["league_code"].fillna("").astype(str).str.upper().str.strip()
cc["Angler"] = (cc["first_name"].fillna("") + " " + cc["surname"].fillna("")).str.strip()
cc.loc[cc["Angler"] == "", "Angler"] = "(unknown)"
cc["weight_kg"] = pd.to_numeric(cc["weight_kg"], errors="coerce").fillna(0.0)
cc["edible"] = cc["edible"].fillna("").astype(str).str.upper()
cc["status"] = cc["status"].fillna("").astype(str)
cc["valid"] = cc["status"].str.startswith("ok")  # resolved + scored

f = cc.copy()
st.caption(f"Showing **{len(f)}** catches (use sidebar filters to narrow).")

# ---- Heaviest catches ---------------------------------------------------
st.subheader("🐟 Heaviest catches")
edible_valid = f[(f["edible"] == "Y") & (f["valid"]) & (f["weight_kg"] > 0)]
non_edible_valid = f[(f["edible"] == "N") & (f["valid"]) & (f["weight_kg"] > 0)]

c1, c2 = st.columns(2)
with c1:
    st.markdown("##### Heaviest Edible")
    if edible_valid.empty:
        st.info("No edible catches yet.")
    else:
        top_e = (edible_valid.sort_values("weight_kg", ascending=False)
                 .head(10)[["comp_id", "Angler", "club", "canonical_species",
                            "length_cm", "weight_kg", "points"]]
                 .rename(columns={"comp_id": "Comp", "club": "Club",
                                  "canonical_species": "Species",
                                  "length_cm": "Length",
                                  "weight_kg": "Weight (kg)",
                                  "points": "Pts"}))
        top_e.insert(0, "Pos.", range(1, len(top_e) + 1))
        st.dataframe(top_e, use_container_width=True, hide_index=True)
        win = top_e.iloc[0]
        st.success(f"🥇 **{win['Angler']}** ({win['Club']}) — "
                   f"{win['Species']} @ {win['Weight (kg)']:.2f} kg "
                   f"in {win['Comp']}")

with c2:
    st.markdown("##### Heaviest Non-Edible")
    if non_edible_valid.empty:
        st.info("No non-edible catches yet.")
    else:
        top_n = (non_edible_valid.sort_values("weight_kg", ascending=False)
                 .head(10)[["comp_id", "Angler", "club", "canonical_species",
                            "length_cm", "weight_kg", "points"]]
                 .rename(columns={"comp_id": "Comp", "club": "Club",
                                  "canonical_species": "Species",
                                  "length_cm": "Length",
                                  "weight_kg": "Weight (kg)",
                                  "points": "Pts"}))
        top_n.insert(0, "Pos.", range(1, len(top_n) + 1))
        st.dataframe(top_n, use_container_width=True, hide_index=True)
        win = top_n.iloc[0]
        st.success(f"🥇 **{win['Angler']}** ({win['Club']}) — "
                   f"{win['Species']} @ {win['Weight (kg)']:.2f} kg "
                   f"in {win['Comp']}")

st.divider()

# ---- Counts per club ----------------------------------------------------
st.subheader("🏛 Catches per club")
counted = f[f["valid"]].copy()  # exclude unknown / sub-minimum

c3, c4 = st.columns(2)
with c3:
    st.markdown("##### Most Edibles per Club")
    e_per_club = (counted[counted["edible"] == "Y"]
                  .groupby("club").size().reset_index(name="Edible catches")
                  .sort_values("Edible catches", ascending=False).reset_index(drop=True))
    if e_per_club.empty:
        st.info("None yet.")
    else:
        e_per_club.insert(0, "Pos.", range(1, len(e_per_club) + 1))
        e_per_club = e_per_club.rename(columns={"club": "Club"})
        st.dataframe(e_per_club, use_container_width=True, hide_index=True)
        st.success(f"🎖 **{e_per_club.iloc[0]['Club']}** — "
                   f"{e_per_club.iloc[0]['Edible catches']} edible(s) "
                   f"(Radio Good Hope)")

with c4:
    st.markdown("##### Most Non-Edibles per Club")
    n_per_club = (counted[counted["edible"] == "N"]
                  .groupby("club").size().reset_index(name="Non-edible catches")
                  .sort_values("Non-edible catches", ascending=False).reset_index(drop=True))
    if n_per_club.empty:
        st.info("None yet.")
    else:
        n_per_club.insert(0, "Pos.", range(1, len(n_per_club) + 1))
        n_per_club = n_per_club.rename(columns={"club": "Club"})
        st.dataframe(n_per_club, use_container_width=True, hide_index=True)

st.divider()

# ---- Most fish per angler ----------------------------------------------
st.subheader("🎣 Most fish per angler")
per_angler = (counted.groupby(["wp_no", "Angler", "club", "league_code"])
              .agg(catches=("comp_id", "count"),
                   total_weight=("weight_kg", "sum"),
                   total_points=("points", "sum"))
              .reset_index()
              .sort_values(["catches", "total_weight"], ascending=[False, False])
              .head(25).reset_index(drop=True))
per_angler.insert(0, "Pos.", range(1, len(per_angler) + 1))
per_angler["total_weight"] = per_angler["total_weight"].round(2)
per_angler["total_points"] = per_angler["total_points"].round(2)
per_angler = per_angler.rename(columns={"wp_no": "WP No", "club": "Club",
                                        "league_code": "Lg",
                                        "catches": "Catches",
                                        "total_weight": "Total Weight (kg)",
                                        "total_points": "Total Pts"})
st.dataframe(per_angler, use_container_width=True, hide_index=True)
