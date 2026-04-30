"""Manage seasons, theme, and danger-zone wipes."""
from __future__ import annotations

import streamlit as st

from app_lib import (clear_all_season_data, clear_catches, create_season,
                     delete_season, list_seasons, load_anglers,
                     load_catches_raw, load_comps, render_season_sidebar,
                     set_active_season)
from theme import (DEFAULT_THEME, PRESETS, load_theme, reset_theme, save_theme)

st.set_page_config(page_title="Settings · WCSAA League", page_icon="⚙", layout="wide")
active = render_season_sidebar()
st.title("⚙ Settings")
seasons = list_seasons()

tab_season, tab_theme, tab_danger = st.tabs(
    ["📅 Seasons", "🎨 Theme & Branding", "⚠ Danger Zone"])

# ---- Seasons ------------------------------------------------------------
with tab_season:
    st.subheader("Active season")
    st.caption("All pages read & write the active season.")
    c1, c2 = st.columns([2, 3])
    with c1:
        pick = st.selectbox("Switch to", seasons,
                            index=seasons.index(active) if active in seasons else 0)
        if st.button("Activate", type="primary", use_container_width=True):
            set_active_season(pick)
            st.success(f"Active season is now **{pick}**.")
            st.rerun()
    with c2:
        a = load_anglers(); c = load_comps(); cr = load_catches_raw()
        st.metric("Active", active)
        st.write(f"**{len(a)}** anglers · **{len(c)}** competitions · **{len(cr)}** catches")

    st.divider()
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

# ---- Theme --------------------------------------------------------------
with tab_theme:
    st.caption("Pick a preset or fine-tune individual colours. Changes apply "
               "to every page (including charts) on save.")

    theme = load_theme()
    ss = st.session_state
    ss.setdefault("_theme_draft", dict(theme))

    def _clear_picker_state():
        """Drop cached color_picker widget state so they re-init from `value=`."""
        for k in list(ss.keys()):
            if k.startswith("cp_"):
                del ss[k]

    col_p, col_a = st.columns([2, 1])
    with col_p:
        preset = st.selectbox("Preset", list(PRESETS.keys()),
                               index=0, key="theme_preset_pick")
    with col_a:
        if st.button("Apply preset", use_container_width=True):
            ss._theme_draft = dict(PRESETS[preset])
            _clear_picker_state()
            st.success(f"Loaded preset: {preset}. Click Save to persist.")
            st.rerun()

    st.divider()
    st.markdown("##### Fine-tune colours")
    draft = ss._theme_draft

    GROUPS = {
        "Layout": ["main_bg", "body_text"],
        "Sidebar": ["sidebar_bg", "sidebar_heading", "sidebar_item",
                     "sidebar_active", "sidebar_active_bg"],
        "Headings & metrics": ["page_heading", "section_heading", "metric_text"],
        "Buttons": ["button_bg", "button_text"],
        "Notifications": ["info_bg", "success_bg", "warning_bg", "error_bg"],
        "Tables & charts": ["leader_highlight", "chart_primary", "chart_accent"],
    }
    for group, keys in GROUPS.items():
        with st.expander(group, expanded=(group == "Sidebar")):
            cols = st.columns(min(len(keys), 4))
            for i, k in enumerate(keys):
                with cols[i % len(cols)]:
                    draft[k] = st.color_picker(
                        k.replace("_", " ").title(),
                        value=draft.get(k, DEFAULT_THEME[k]),
                        key=f"cp_{k}",
                    )

    st.divider()
    st.markdown("##### Live preview")
    pv1, pv2, pv3 = st.columns(3)
    pv1.markdown(
        f"<div style='background:{draft['main_bg']};color:{draft['body_text']};"
        f"border:1px solid #ccc;border-radius:8px;padding:12px'>"
        f"<h4 style='color:{draft['page_heading']};margin:0 0 6px'>Page heading</h4>"
        f"<p style='margin:0;color:{draft['section_heading']}'>Section text</p>"
        f"</div>", unsafe_allow_html=True)
    pv2.markdown(
        f"<div style='background:{draft['sidebar_bg']};color:{draft['sidebar_item']};"
        f"border-radius:8px;padding:12px'>"
        f"<h4 style='color:{draft['sidebar_heading']};margin:0 0 6px'>Sidebar</h4>"
        f"<div style='background:{draft['sidebar_active_bg']};color:{draft['sidebar_active']};"
        f"padding:6px 8px;border-radius:6px'>Active item</div>"
        f"</div>", unsafe_allow_html=True)
    pv3.markdown(
        f"<div style='background:{draft['main_bg']};border:1px solid #ccc;"
        f"border-radius:8px;padding:12px'>"
        f"<button style='background:{draft['button_bg']};color:{draft['button_text']};"
        f"border:none;border-radius:6px;padding:8px 14px;font-weight:600'>"
        f"Primary button</button>"
        f"<div style='margin-top:10px;background:{draft['leader_highlight']};"
        f"padding:6px 8px;border-radius:6px'>🥇 Leader row</div>"
        f"<div style='margin-top:8px'>"
        f"<span style='display:inline-block;width:18px;height:18px;background:"
        f"{draft['chart_primary']};border-radius:3px;vertical-align:middle'></span> "
        f"Chart primary &nbsp;"
        f"<span style='display:inline-block;width:18px;height:18px;background:"
        f"{draft['chart_accent']};border-radius:3px;vertical-align:middle'></span> "
        f"Chart accent</div>"
        f"</div>", unsafe_allow_html=True)

    s1, s2, _ = st.columns([1, 1, 4])
    if s1.button("💾 Save theme", type="primary", use_container_width=True):
        save_theme(draft)
        st.success("Theme saved. Reloading…")
        st.rerun()
    if s2.button("↺ Reset to default", use_container_width=True):
        reset_theme()
        ss._theme_draft = dict(DEFAULT_THEME)
        _clear_picker_state()
        st.success("Theme reset to default.")
        st.rerun()

# ---- Danger zone --------------------------------------------------------
with tab_danger:
    st.caption("These actions are irreversible. They only affect the **active "
               "season** unless stated otherwise.")

    with st.expander("🗑️ Clear catches only (keeps anglers + competitions)"):
        st.warning(f"This will delete every catch recorded in **{active}**.")
        confirm = st.text_input("Type the season label to confirm", key="cc_conf")
        if st.button("Clear catches", type="secondary", disabled=(confirm != active)):
            clear_catches()
            st.success(f"Cleared all catches in {active}.")
            st.rerun()

    with st.expander("🧹 Clear ALL season data (anglers + competitions + catches)"):
        st.error(f"This wipes anglers, competitions and catches in **{active}**. "
                 "Species master is preserved.")
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
