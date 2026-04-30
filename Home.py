"""WCSAA League — Streamlit app entry point.

Run:  streamlit run Home.py
"""
from __future__ import annotations

import streamlit as st

from app_lib import (EDIBLE_PTS_PER_KG, NON_EDIBLE_PTS_PER_KG, get_logo_bytes,
                     load_anglers, load_catches_scored, load_comps,
                     manage_logo, render_season_sidebar)
from standings import BEST_N_DEFAULT, apply_best_n, per_entity_per_comp

st.set_page_config(page_title="WCSAA League", page_icon="🎣", layout="wide")
active = render_season_sidebar()

# ---- Header (logo left · title right) -----------------------------------
hcol_logo, hcol_text = st.columns([1, 4], vertical_alignment="center")
with hcol_logo:
    logo = get_logo_bytes("wcsaa")
    if logo:
        st.image(logo, width=160)
    else:
        st.markdown(
            "<div style='width:160px;height:160px;border:2px dashed #ccc;"
            "border-radius:12px;display:flex;align-items:center;justify-content:center;"
            "color:#888;font-weight:600;'>WCSAA<br>logo</div>",
            unsafe_allow_html=True,
        )
with hcol_text:
    st.title("WCSAA League")
    st.caption(f"Season **{active}** — manage anglers, competitions and catches, "
               f"view live standings, print to PDF.")

st.divider()

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

    comp_order = sorted(catches["comp_id"].unique().tolist())
    use_best_n = st.toggle(f"Best {BEST_N_DEFAULT} of {len(comp_order)}",
                           value=False, key="home_best_n",
                           help="Drop each entity's lowest scores so only the "
                                f"best {BEST_N_DEFAULT} comps count.")
    n_eff = BEST_N_DEFAULT if use_best_n else 10**6

    left, right = st.columns(2)
    with left:
        st.subheader("Club Standings")
        m = per_entity_per_comp(cc, "club", comp_order)
        _, _, total = apply_best_n(m, n=n_eff)
        club_tot = total.sort_values(ascending=False).reset_index()
        club_tot.columns = ["Club", "Points"]
        club_tot.insert(0, "Pos.", range(1, len(club_tot) + 1))
        st.dataframe(club_tot, use_container_width=True, hide_index=True)
    with right:
        st.subheader("Top 10 Individuals")
        top = cc.merge(anglers[["wp_no", "first_name", "surname"]], on="wp_no", how="left")
        top["Angler"] = (top["first_name"].fillna("") + " " + top["surname"].fillna("")).str.strip()
        m = per_entity_per_comp(top, "wp_no", comp_order)
        _, _, total = apply_best_n(m, n=n_eff)
        meta = top.drop_duplicates("wp_no").set_index("wp_no")[["Angler", "club"]]
        ind = total.to_frame("Points").join(meta).reset_index()
        ind = ind.sort_values("Points", ascending=False).head(10).reset_index(drop=True)
        ind.insert(0, "Pos.", range(1, len(ind) + 1))
        ind = ind.rename(columns={"wp_no": "WP No", "club": "Club"})
        st.dataframe(ind[["Pos.", "WP No", "Angler", "Club", "Points"]],
                     use_container_width=True, hide_index=True)
else:
    st.info("No catches yet — head to **Catches** in the sidebar to add some.")

st.divider()

with st.expander("Scoring rule"):
    st.markdown(f"""
- **Edible fish** (Bony Fishes) = **{EDIBLE_PTS_PER_KG:.0f} points per kg** — under **0.50 kg** scores 0
- **Non-edible fish** (Sharks / Rays / Guitarfish) = **{NON_EDIBLE_PTS_PER_KG:.0f} point per kg** — under **1.00 kg** scores 0
- **Gurnards & Catfish (Barbel)** = **1 point per fish flat** (overrides weight + edible)
- **St Joseph** (Elephant Fish) = treated as **edible**
- All scores are **floored to 2 decimal places** (e.g. 1.499 kg × 4 = 5.99)
- **Site Fish (...)** = 1.00 kg flat (then × points-per-kg above)
- **`< X kg`** suffix = 0 points (sub-minimum)
- Catshark (Brown), Catshark (Puffadder) = 0 points (zero-score list)
- Weight: `W_kg = exp(log_a + b · ln(length_cm))` — SASAA formula
""")

with st.expander("WCSAA logo"):
    manage_logo("wcsaa", label="Upload / replace WCSAA logo", width=180,
                placeholder="No WCSAA logo yet — upload one below.")
