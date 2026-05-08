"""Manage clubs — pick a club, then add / edit / remove its anglers."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib import (CLUBS, DIVISION_CODES, DIVISIONS, SUB_TEAMS,
                     get_logo_bytes, load_anglers, manage_logo,
                     render_season_sidebar, save_anglers)
from ui import divider_label, kpi_row, page_header, section_label

st.set_page_config(page_title="Clubs · WCSAA League", page_icon="🏛️", layout="wide")
active = render_season_sidebar()
page_header("Clubs & Anglers", "Manage rosters, divisions and logos per club",
            "🏛️", active)

all_anglers  = load_anglers()
known_clubs  = sorted(set(CLUBS) | set(c for c in all_anglers["club"].unique() if c))

# ── Club picker ───────────────────────────────────────────────────────────
club = st.selectbox(
    "Select club",
    known_clubs,
    index=known_clubs.index(CLUBS[0]) if CLUBS[0] in known_clubs else 0,
)

club_df   = all_anglers[all_anglers["club"] == club].copy().reset_index(drop=True)
others_df = all_anglers[all_anglers["club"] != club].copy()

# ── Club header ───────────────────────────────────────────────────────────
img = get_logo_bytes(f"club_{club}")
if img:
    hc_logo, hc_info = st.columns([1, 6], vertical_alignment="center")
    with hc_logo:
        st.image(img, width=100)
    with hc_info:
        st.markdown(f"### {club}")
        st.caption(f"**{len(club_df)}** anglers registered")
else:
    st.markdown(f"### {club}")
    st.caption(f"**{len(club_df)}** anglers registered")

# ── Club KPIs ─────────────────────────────────────────────────────────────
if not club_df.empty:
    div_counts = club_df["league_code"].value_counts()
    kpi_row([
        {"icon": "👥", "label": "Total anglers", "value": len(club_df)},
        {"icon": "🏅", "label": "Masters (M)",
         "value": int(div_counts.get("M", 0))},
        {"icon": "⭐", "label": "Seniors (S)",
         "value": int(div_counts.get("S", 0))},
        {"icon": "🌟", "label": "Other divisions",
         "value": len(club_df) - int(div_counts.get("M", 0)) - int(div_counts.get("S", 0))},
    ])

# ── Logo management ───────────────────────────────────────────────────────
with st.expander(f"⚙ {club} logo"):
    manage_logo(f"club_{club}", label=f"Upload / replace {club} logo", width=130,
                placeholder=f"No logo for {club} yet.")

# ── Angler roster editor ──────────────────────────────────────────────────
divider_label("Angler Roster")
st.caption("Sub-team is the angler's *default* — actual per-competition teams are set on the **Competitions** page.")

edit_cols = ["wp_no", "sasaa_no", "first_name", "surname",
             "sub_team", "league_code", "league_division"]
view = club_df[edit_cols] if not club_df.empty else pd.DataFrame(columns=edit_cols)

edited = st.data_editor(
    view, num_rows="dynamic", use_container_width=True,
    column_config={
        "wp_no":           st.column_config.TextColumn("WP No", required=True),
        "sasaa_no":        st.column_config.TextColumn("SASAA No"),
        "first_name":      st.column_config.TextColumn("First name", required=True),
        "surname":         st.column_config.TextColumn("Surname", required=True),
        "sub_team":        st.column_config.SelectboxColumn(
                               "Sub-team", options=[""] + SUB_TEAMS,
                               help="A–I → PNTS_A .. PNTS_I"),
        "league_code":     st.column_config.SelectboxColumn(
                               "Division code", options=[""] + DIVISION_CODES,
                               help=" / ".join(f"{k}={v}" for k, v in DIVISIONS.items())),
        "league_division": st.column_config.TextColumn(
                               "Division label",
                               help="Auto-filled from code if left blank"),
    },
    key=f"club_editor_{club}",
)

c_save, _ = st.columns([1, 5])
if c_save.button("💾 Save roster", type="primary", use_container_width=True):
    edited = edited.copy()
    edited["club"] = club
    edited["league_division"] = edited.apply(
        lambda r: r["league_division"] if r["league_division"]
        else DIVISIONS.get((r["league_code"] or "").upper(), ""),
        axis=1,
    )
    merged = pd.concat([others_df, edited], ignore_index=True)
    save_anglers(merged)
    st.success(f"Saved {len(edited)} anglers for **{club}**.")
    st.rerun()

# ── Sub-team summary ──────────────────────────────────────────────────────
if not club_df.empty:
    with st.expander("Sub-team breakdown"):
        by_team = (club_df["sub_team"].fillna("").replace("", "—")
                   .value_counts().rename_axis("Sub-team").reset_index(name="Anglers"))
        st.dataframe(by_team, use_container_width=False, hide_index=True)

# ── Division reference ────────────────────────────────────────────────────
with st.expander("Division code reference"):
    st.markdown("\n".join(f"- **{k}** — {v}" for k, v in DIVISIONS.items()))
