"""4OAC League — Streamlit app entry point.

Run:  streamlit run Home.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib import (EDIBLE_PTS_PER_KG, NON_EDIBLE_PTS_PER_KG, load_anglers,
                     load_catches_scored, load_comps, render_season_sidebar)

st.set_page_config(page_title="4OAC League", page_icon="🎣", layout="wide")
active = render_season_sidebar()

st.title("🎣 4OAC League")
st.caption(f"Season **{active}** — manage anglers, competitions and catches, view live standings, print to PDF.")

anglers = load_anglers()
comps = load_comps()
catches = load_catches_scored()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Competitions", len(comps))
c2.metric("Anglers", len(anglers))
c3.metric("Catches", len(catches))
c4.metric("Total Points", f"{catches['points'].sum():,.0f}" if len(catches) else "0")

st.divider()

if len(catches):
    cc = catches.merge(anglers[["wp_no", "club"]], on="wp_no", how="left")
    cc["club"] = cc["club"].fillna("UNKNOWN").replace("", "UNKNOWN")

    left, right = st.columns(2)

    with left:
        st.subheader("Club Standings")
        club_tot = (cc.groupby("club", as_index=False)["points"].sum()
                    .sort_values("points", ascending=False).reset_index(drop=True))
        club_tot.insert(0, "Rank", range(1, len(club_tot) + 1))
        club_tot = club_tot.rename(columns={"club": "Club", "points": "Points"})
        st.dataframe(club_tot, use_container_width=True, hide_index=True)

    with right:
        st.subheader("Top 10 Individuals")
        top = cc.merge(anglers[["wp_no", "first_name", "surname"]], on="wp_no", how="left")
        top["Angler"] = (top["first_name"].fillna("") + " " + top["surname"].fillna("")).str.strip()
        ind = (top.groupby(["wp_no", "Angler", "club"], as_index=False)["points"].sum()
               .sort_values("points", ascending=False).head(10).reset_index(drop=True))
        ind.insert(0, "Rank", range(1, len(ind) + 1))
        ind = ind.rename(columns={"wp_no": "WP No", "club": "Club", "points": "Points"})
        st.dataframe(ind, use_container_width=True, hide_index=True)
else:
    st.info("No catches yet — head to **Catches** in the sidebar to add some.")

st.divider()

with st.expander("Scoring rule"):
    st.markdown(f"""
- **Edible fish** (Bony Fishes) = **{EDIBLE_PTS_PER_KG:.0f} points per kg**
- **Non-edible fish** (Sharks / Rays / Guitarfish) = **{NON_EDIBLE_PTS_PER_KG:.0f} point per kg**
- **Site Fish (...)** = 1.00 kg flat (then × points-per-kg above)
- **`< X kg`** suffix = 0 points (sub-minimum)
- Catshark (Brown / Puffadder), Skate (Biscuit) = 0 points
- Weight: `W_kg = exp(log_a + b · ln(length_cm))` — SASAA formula
""")
