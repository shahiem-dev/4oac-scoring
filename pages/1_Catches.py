"""Capture catches — sticky comp + angler for fast bulk entry."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib import (SUB_TEAMS, angler_options, comp_options, get_scorer,
                     load_anglers, load_catches_raw, load_catches_scored,
                     load_team_assignments, parse_wp_from_label,
                     render_season_sidebar, save_catches_raw,
                     save_team_assignments, species_choices)

st.set_page_config(page_title="Catches · WCSAA League", page_icon="🐟", layout="wide")
active = render_season_sidebar()
st.title(f"🐟 Catches — {active}")

comps = comp_options()
anglers = angler_options()
species = species_choices()

if not comps:
    st.warning("No competitions yet — add one on the **Competitions** page first.")
    st.stop()
if not anglers:
    st.warning("No anglers yet — add some on the **Anglers** page first.")
    st.stop()

# ---- Capture (sticky comp + angler) -------------------------------------
st.subheader("Capture catch")
ss = st.session_state
ss.setdefault("cap_comp", comps[-1])
ss.setdefault("cap_angler", anglers[0])
ss.setdefault("cap_species", species[0] if species else "")

c1, c2 = st.columns(2)
ss.cap_comp = c1.selectbox("Competition", comps,
                           index=comps.index(ss.cap_comp) if ss.cap_comp in comps else len(comps) - 1,
                           key="sel_comp")
ss.cap_angler = c2.selectbox("Angler", anglers,
                             index=anglers.index(ss.cap_angler) if ss.cap_angler in anglers else 0,
                             key="sel_angler")

wp_current = parse_wp_from_label(ss.cap_angler)
team_opts = [""] + SUB_TEAMS
ta = load_team_assignments()
existing = ta[(ta["comp_id"] == ss.cap_comp) & (ta["wp_no"] == wp_current)]
assigned_team = str(existing.iloc[0]["sub_team"] or "") if len(existing) else ""

ct1, ct2, ct3 = st.columns([3, 1, 1])
sp_idx = species.index(ss.cap_species) if ss.cap_species in species else 0
ss.cap_species = ct1.selectbox("Species (as written on slip)", species,
                               index=sp_idx, key="sel_species")
if assigned_team:
    team_pick = assigned_team
    ct3.markdown(f"**Team (this comp)**\n\n🏷️ `{assigned_team}` — set on Competitions page")
else:
    team_pick = ct3.selectbox("Team (this comp)", team_opts, index=0,
                              key=f"sel_team_{ss.cap_comp}_{wp_current}",
                              help="No team set in Competitions → Team Selection. "
                                   "Optionally pick one here; it will be saved on Add catch.")
with st.form("add_catch", clear_on_submit=False):
    length = ct2.number_input("Length (cm)", min_value=0.0, step=0.5, value=0.0,
                              key="cap_length")
    submitted = st.form_submit_button("➕ Add catch", type="primary", use_container_width=True)
    if submitted:
        from app_lib import points_for
        wp = parse_wp_from_label(ss.cap_angler)
        sp = ss.cap_species
        ta_now = load_team_assignments()
        mask = (ta_now["comp_id"] == ss.cap_comp) & (ta_now["wp_no"] == wp)
        ta_now = ta_now[~mask]
        if team_pick:
            ta_now = pd.concat([ta_now, pd.DataFrame([{
                "comp_id": ss.cap_comp, "wp_no": wp, "sub_team": team_pick}])],
                ignore_index=True)
        save_team_assignments(ta_now)
        scorer = get_scorer()
        res = scorer.score(sp, length if length > 0 else None)
        raw = load_catches_raw()
        new_row = pd.DataFrame([{"comp_id": ss.cap_comp, "wp_no": wp,
                                 "species_raw": sp,
                                 "length_cm": str(length) if length > 0 else ""}])
        save_catches_raw(pd.concat([raw, new_row], ignore_index=True))
        if res.canonical_name is None and res.note == "error:unknown_species":
            st.error(f"Saved, but **{sp}** is unmatched — scoring 0 until the species master/aliases are updated.")
        else:
            pts = points_for(res.weight_kg, res.edible, res.canonical_name)
            st.success(f"✓ {ss.cap_comp} · {ss.cap_angler} · {sp} @ {length}cm → "
                       f"**{res.weight_kg:.2f} kg** = **{pts:.2f} pts** ({res.note})")

st.divider()

# ---- All catches table --------------------------------------------------
st.subheader("All catches (this season)")
raw = load_catches_raw()
if len(raw):
    flt = st.multiselect("Filter by competition", comps, default=[],
                         key="all_catches_filter",
                         help="Leave empty to show all. Editing while filtered only saves the filtered rows + unedited rest.")
    view_raw = raw if not flt else raw[raw["comp_id"].isin(flt)].reset_index(drop=True)
    edited = st.data_editor(
        view_raw, num_rows="dynamic", use_container_width=True,
        column_config={
            "comp_id": st.column_config.SelectboxColumn("Comp", options=comps, required=True),
            "wp_no": st.column_config.TextColumn("WP No", required=True),
            "species_raw": st.column_config.TextColumn("Species", required=True),
            "length_cm": st.column_config.TextColumn("Length (cm)"),
        },
        key="catch_editor",
    )
    if st.button("💾 Save changes", type="primary"):
        if flt:
            kept = raw[~raw["comp_id"].isin(flt)]
            merged = pd.concat([kept, edited], ignore_index=True)
        else:
            merged = edited
        save_catches_raw(merged)
        st.success(f"Saved {len(merged)} catches and rescored.")
        st.rerun()

    st.divider()
    st.subheader("Scored")
    scored = load_catches_scored()
    if len(scored):
        comp_filter = st.multiselect("Filter by competition", comps, default=[])
        view = scored if not comp_filter else scored[scored["comp_id"].isin(comp_filter)]
        st.dataframe(view, use_container_width=True, hide_index=True)
        unknown = scored[scored["status"] == "error:unknown_species"]
        if len(unknown):
            with st.expander(f"⚠ {len(unknown)} unknown species (scoring 0)"):
                st.dataframe(unknown[["comp_id", "wp_no", "species_raw"]],
                             use_container_width=True, hide_index=True)
else:
    st.info("No catches yet — use the form above to capture one.")
