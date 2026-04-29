"""Manage clubs — pick a club, then add/edit/remove its anglers + sub-teams."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib import (CLUBS, DIVISION_CODES, DIVISIONS, SUB_TEAMS,
                     get_logo_bytes, load_anglers, manage_logo,
                     render_season_sidebar, save_anglers)

st.set_page_config(page_title="Clubs · WCSAA League", page_icon="🏛️", layout="wide")
active = render_season_sidebar()
st.title(f"🏛️ Clubs — {active}")
st.caption("Pick a club to edit its angler roster and logo. Sub-team is the angler's *default* — actual per-comp teams are set on the **Competitions** page.")

all_anglers = load_anglers()
known_clubs = sorted(set(CLUBS) | set(c for c in all_anglers["club"].unique() if c))
club = st.selectbox("Club", known_clubs, index=known_clubs.index(CLUBS[0]) if CLUBS[0] in known_clubs else 0)

club_df = all_anglers[all_anglers["club"] == club].copy().reset_index(drop=True)
others_df = all_anglers[all_anglers["club"] != club].copy()

# ---- Club header (logo + summary) ----
hl, ht = st.columns([1, 5], vertical_alignment="center")
with hl:
    img = get_logo_bytes(f"club_{club}")
    if img:
        st.image(img, width=120)
    else:
        st.markdown(
            "<div style='width:120px;height:120px;border:2px dashed #ccc;"
            "border-radius:10px;display:flex;align-items:center;justify-content:center;"
            "color:#999;font-size:11px;text-align:center;'>No logo</div>",
            unsafe_allow_html=True,
        )
with ht:
    st.markdown(f"### {club}")
    st.caption(f"**{len(club_df)}** anglers currently registered.")

with st.expander(f"{club} logo"):
    manage_logo(f"club_{club}", label=f"Upload / replace {club} logo", width=140,
                placeholder=f"No logo for {club} yet — upload one.")

# Summary by sub-team
if len(club_df):
    by_team = (club_df["sub_team"].fillna("").replace("", "—")
               .value_counts().rename_axis("Sub-team").reset_index(name="Anglers"))
    st.dataframe(by_team, use_container_width=False, hide_index=True)

# Editable table
edit_cols = ["wp_no", "sasaa_no", "first_name", "surname",
             "sub_team", "league_code", "league_division"]
view = club_df[edit_cols] if len(club_df) else pd.DataFrame(columns=edit_cols)

edited = st.data_editor(
    view, num_rows="dynamic", use_container_width=True,
    column_config={
        "wp_no": st.column_config.TextColumn("WP No", required=True),
        "sasaa_no": st.column_config.TextColumn("SASAA No"),
        "first_name": st.column_config.TextColumn("First name", required=True),
        "surname": st.column_config.TextColumn("Surname", required=True),
        "sub_team": st.column_config.SelectboxColumn("Sub-team", options=[""] + SUB_TEAMS,
                                                    help="A–I → PNTS_A..PNTS_I"),
        "league_code": st.column_config.SelectboxColumn(
            "Division", options=[""] + DIVISION_CODES,
            help=" / ".join(f"{k}={v}" for k, v in DIVISIONS.items())),
        "league_division": st.column_config.TextColumn("Division (free text)",
                                                       help="Optional descriptive label"),
    },
    key=f"club_editor_{club}",
)

c1, c2 = st.columns([1, 5])
if c1.button("💾 Save", type="primary"):
    edited = edited.copy()
    edited["club"] = club
    # Auto-fill league_division from code if blank
    edited["league_division"] = edited.apply(
        lambda r: r["league_division"] if r["league_division"]
        else DIVISIONS.get((r["league_code"] or "").upper(), ""),
        axis=1,
    )
    merged = pd.concat([others_df, edited], ignore_index=True)
    save_anglers(merged)
    st.success(f"Saved {len(edited)} anglers in {club}.")
    st.rerun()

st.divider()
with st.expander("Division codes"):
    st.markdown("\n".join(f"- **{k}** — {v}" for k, v in DIVISIONS.items()))
