"""Manage competitions (IC events)."""
from __future__ import annotations

import streamlit as st

from app_lib import load_comps, render_season_sidebar, save_comps

st.set_page_config(page_title="Competitions · 4OAC League", page_icon="📅", layout="wide")
active = render_season_sidebar()
st.title(f"📅 Competitions — {active}")
st.caption("One row per Inter-Club. comp_id e.g. 'IC 8'.")

df = load_comps()
edited = st.data_editor(
    df, num_rows="dynamic", use_container_width=True,
    column_config={
        "comp_id": st.column_config.TextColumn("Comp ID", required=True),
        "date": st.column_config.TextColumn("Date (YYYY-MM-DD)"),
        "venue": st.column_config.TextColumn("Venue"),
    },
    key="comp_editor",
)
if st.button("💾 Save", type="primary"):
    save_comps(edited)
    st.success(f"Saved {len(edited)} competitions.")
    st.rerun()
