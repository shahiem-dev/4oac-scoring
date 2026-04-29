"""Manage seasons, switch between them, clear data."""
from __future__ import annotations

import streamlit as st

from app_lib import (clear_all_season_data, clear_catches, create_season,
                     delete_season, list_seasons, load_anglers,
                     load_catches_raw, load_comps, render_season_sidebar,
                     set_active_season)

st.set_page_config(page_title="Settings · WCSAA League", page_icon="⚙", layout="wide")
active = render_season_sidebar()
st.title("⚙ Settings")
seasons = list_seasons()

# ---- Active season -------------------------------------------------------
st.subheader("Active season")
st.caption("All pages (Anglers, Competitions, Catches, Standings, Reports) read & write the active season.")

c1, c2 = st.columns([2, 3])
with c1:
    pick = st.selectbox("Switch to", seasons, index=seasons.index(active) if active in seasons else 0)
    if st.button("Activate", type="primary", use_container_width=True):
        set_active_season(pick)
        st.success(f"Active season is now **{pick}**.")
        st.rerun()
with c2:
    a = load_anglers(); c = load_comps(); cr = load_catches_raw()
    st.metric("Active", active)
    st.write(f"**{len(a)}** anglers · **{len(c)}** competitions · **{len(cr)}** catches")

st.divider()

# ---- Create season -------------------------------------------------------
st.subheader("Start a new season")
with st.form("new_season"):
    name = st.text_input("Season label", placeholder="e.g. 2026-27",
                         help="Letters, numbers, '-' or '_' only.")
    carry = st.checkbox("Carry over angler roster from current season", value=True)
    activate = st.checkbox("Activate the new season immediately", value=True)
    if st.form_submit_button("Create season", type="primary"):
        try:
            new = create_season(name, carry_anglers_from=active if carry else None)
            if activate:
                set_active_season(new)
            st.success(f"Created season **{new}**" + (" and activated." if activate else "."))
            st.rerun()
        except ValueError as e:
            st.error(str(e))

st.divider()

# ---- Danger zone ---------------------------------------------------------
st.subheader("Danger zone")
st.caption("These actions are irreversible. They only affect the **active season** unless stated otherwise.")

with st.expander("🗑️ Clear catches only (keeps anglers + competitions)"):
    st.warning(f"This will delete every catch recorded in **{active}**.")
    confirm = st.text_input("Type the season label to confirm", key="cc_conf")
    if st.button("Clear catches", type="secondary", disabled=(confirm != active)):
        clear_catches()
        st.success(f"Cleared all catches in {active}.")
        st.rerun()

with st.expander("🧹 Clear ALL season data (anglers + competitions + catches)"):
    st.error(f"This wipes anglers, competitions and catches in **{active}**. Species master is preserved.")
    confirm = st.text_input("Type the season label to confirm", key="ca_conf")
    if st.button("Clear all data", type="secondary", disabled=(confirm != active)):
        clear_all_season_data()
        st.success(f"Wiped {active}.")
        st.rerun()

with st.expander("❌ Delete a season entirely"):
    st.error("Removes the season folder and all its CSVs from disk.")
    target = st.selectbox("Season to delete", seasons, key="del_pick")
    confirm = st.text_input("Type the season label to confirm", key="del_conf")
    if st.button("Delete season", type="secondary", disabled=(confirm != target)):
        delete_season(target)
        st.success(f"Deleted {target}.")
        st.rerun()
