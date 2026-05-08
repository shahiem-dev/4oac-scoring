"""WCSAA League — dashboard home page."""
from __future__ import annotations

import streamlit as st

from app_lib import (EDIBLE_PTS_PER_KG, NON_EDIBLE_PTS_PER_KG, apply_filters,
                     get_logo_bytes, load_anglers, load_catches_scored,
                     load_comps, manage_logo, render_global_filters,
                     render_season_sidebar)
from standings import BEST_N_DEFAULT, apply_best_n, per_entity_per_comp
from ui import divider_label, kpi_row, leader_banner, page_header, section_label

st.set_page_config(page_title="WCSAA League", page_icon="🎣", layout="wide")
active = render_season_sidebar()

# ── Header ────────────────────────────────────────────────────────────────
logo = get_logo_bytes("wcsaa")
if logo:
    col_logo, col_hdr = st.columns([1, 6], vertical_alignment="center")
    with col_logo:
        st.image(logo, width=110)
    with col_hdr:
        page_header("WCSAA League",
                    "Western Cape Shore Angling Association · Live scoring & standings",
                    season=active)
else:
    page_header("WCSAA League",
                "Western Cape Shore Angling Association · Live scoring & standings",
                icon="🎣", season=active)

# ── Data load ─────────────────────────────────────────────────────────────
anglers = load_anglers()
comps   = load_comps()
catches = load_catches_scored()

if not catches.empty:
    filters = render_global_filters(catches, anglers)
    catches, anglers = apply_filters(catches, anglers, filters)

# ── KPI row ───────────────────────────────────────────────────────────────
total_pts = f"{catches['points'].sum():,.0f}" if not catches.empty else "0"
kpi_row([
    {"icon": "📅", "label": "Competitions",  "value": len(comps)},
    {"icon": "🎣", "label": "Anglers",        "value": len(anglers)},
    {"icon": "🐟", "label": "Catches",        "value": len(catches)},
    {"icon": "⭐", "label": "Total Points",   "value": total_pts},
])

# ── Standings ─────────────────────────────────────────────────────────────
if not catches.empty:
    cc = catches.merge(anglers[["wp_no", "club"]], on="wp_no", how="left")
    cc["club"] = cc["club"].fillna("UNKNOWN").replace("", "UNKNOWN")
    comp_order = sorted(catches["comp_id"].unique().tolist())

    use_best_n = st.toggle(
        f"Best {BEST_N_DEFAULT} of {len(comp_order)} competitions",
        value=False, key="home_best_n",
        help=f"Drop each entity's lowest scores so only the best "
             f"{BEST_N_DEFAULT} competitions count.")
    n_eff = BEST_N_DEFAULT if use_best_n else 10**6

    left, right = st.columns(2)

    with left:
        with st.container(border=True):
            section_label("Club Standings")
            m = per_entity_per_comp(cc, "club", comp_order)
            _, _, total = apply_best_n(m, n=n_eff)
            club_tot = total.sort_values(ascending=False).reset_index()
            club_tot.columns = ["Club", "Points"]
            club_tot.insert(0, "Pos.", range(1, len(club_tot) + 1))
            st.dataframe(club_tot, use_container_width=True, hide_index=True)
            if not club_tot.empty:
                w = club_tot.iloc[0]
                leader_banner("🥇", w["Club"],
                              pts=f"{w['Points']:,.2f} pts")

    with right:
        with st.container(border=True):
            section_label("Top 10 Individuals")
            top = cc.merge(
                anglers[["wp_no", "first_name", "surname"]], on="wp_no", how="left")
            top["Angler"] = (top["first_name"].fillna("") + " "
                             + top["surname"].fillna("")).str.strip()
            m = per_entity_per_comp(top, "wp_no", comp_order)
            _, _, total = apply_best_n(m, n=n_eff)
            meta = top.drop_duplicates("wp_no").set_index("wp_no")[["Angler", "club"]]
            ind = (total.to_frame("Points").join(meta).reset_index()
                   .sort_values("Points", ascending=False).head(10)
                   .reset_index(drop=True))
            ind.insert(0, "Pos.", range(1, len(ind) + 1))
            ind = ind.rename(columns={"wp_no": "WP No", "club": "Club"})
            st.dataframe(ind[["Pos.", "WP No", "Angler", "Club", "Points"]],
                         use_container_width=True, hide_index=True)
            if not ind.empty:
                w = ind.iloc[0]
                leader_banner("🥇", w["Angler"], detail=w["Club"],
                              pts=f"{w['Points']:,.2f} pts")
else:
    st.info("No catches yet — head to **Catches** in the sidebar to start capturing.")

# ── Scoring rule ──────────────────────────────────────────────────────────
divider_label("Scoring Rules")
with st.expander("View scoring rules"):
    st.markdown(f"""
- **Edible fish** = **{EDIBLE_PTS_PER_KG:.0f} pts/kg** — minimum **0.50 kg** (below = 0 pts)
- **Non-edible fish** = **{NON_EDIBLE_PTS_PER_KG:.0f} pt/kg** — minimum **1.00 kg** (below = 0 pts)
- **Gurnards & Catfish (Barbel)** = **1 point flat** per fish (overrides weight)
- **St Joseph** (Elephant Fish) = treated as edible
- All scores floored to 2 decimal places (e.g. 1.499 kg × 4 = 5.99)
- **Site Fish** = 1.00 kg flat (then × pts/kg rule above)
- **`< X kg`** suffix = 0 pts (sub-minimum)
- Catshark (Brown), Catshark (Puffadder) = 0 pts
""")

# ── Logo management ───────────────────────────────────────────────────────
with st.expander("⚙ Manage WCSAA logo"):
    manage_logo("wcsaa", label="Upload / replace WCSAA logo", width=180,
                placeholder="No WCSAA logo yet — upload one below.")
