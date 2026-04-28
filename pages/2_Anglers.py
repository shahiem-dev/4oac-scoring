"""Manage the angler roster."""
from __future__ import annotations

import streamlit as st

from app_lib import load_anglers, render_season_sidebar, save_anglers

st.set_page_config(page_title="Anglers · 4OAC League", page_icon="👥", layout="wide")
active = render_season_sidebar()
st.title(f"👥 Anglers — {active}")
st.caption("Edit names, club, sub-team and league code. WP No must be unique.")

df = load_anglers()
edited = st.data_editor(
    df, num_rows="dynamic", use_container_width=True,
    column_config={
        "wp_no": st.column_config.TextColumn("WP No", required=True),
        "sasaa_no": st.column_config.TextColumn("SASAA No"),
        "first_name": st.column_config.TextColumn("First name"),
        "surname": st.column_config.TextColumn("Surname"),
        "club": st.column_config.TextColumn("Club"),
        "sub_team": st.column_config.TextColumn("Sub-team"),
        "league_division": st.column_config.TextColumn("League division"),
        "league_code": st.column_config.SelectboxColumn(
            "Lg", options=["S", "M", "G", "J", "K", "L", ""],
        ),
    },
    key="ang_editor",
)
if st.button("💾 Save", type="primary"):
    save_anglers(edited)
    st.success(f"Saved {len(edited)} anglers.")
    st.rerun()
