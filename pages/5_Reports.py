"""Generate printable XLSX reports and the master tracker workbook."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import streamlit as st

from auth import require_login
require_login()

import pandas as pd

from app_lib import (ROOT, apply_filters, comp_options, load_anglers,
                     load_catches_scored, load_comps, render_global_filters,
                     render_season_sidebar)
from ui import divider_label, empty_state, kpi_row, page_header, section_label

st.set_page_config(page_title="Reports · WCSAA League", page_icon="📑", layout="wide")
active      = render_season_sidebar()
REPORTS_DIR = ROOT / "reports" / active
page_header("Reports & Exports", "Generate XLSX reports and the master tracker workbook",
            "📑", active)


def run(cmd: list[str]) -> tuple[bool, str]:
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return res.returncode == 0, (res.stdout + res.stderr).strip()


comps = comp_options()

# ── All anglers download (CSV + XLSX) ─────────────────────────────────────
import io
divider_label("All anglers — quick export")
all_anglers_df = load_anglers()
if all_anglers_df.empty:
    empty_state("No anglers in this season yet.", "🎣")
else:
    # Friendly column order + headers
    display_cols = ["wp_no", "sasaa_no", "first_name", "surname", "club",
                    "sub_team", "league_code", "league_division"]
    display_cols = [c for c in display_cols if c in all_anglers_df.columns]
    df = all_anglers_df[display_cols].copy()
    df = df.sort_values(["club", "surname", "first_name"], na_position="last")
    pretty = df.rename(columns={
        "wp_no": "WP No", "sasaa_no": "SASAA No",
        "first_name": "First Name", "surname": "Surname",
        "club": "Club", "sub_team": "Sub-team",
        "league_code": "Division Code", "league_division": "Division",
    })

    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        kpi_row([
            {"icon": "👥", "label": "Anglers", "value": len(pretty)},
            {"icon": "🏠", "label": "Clubs",   "value": pretty["Club"].nunique()},
        ])
    with c2:
        st.download_button(
            "⬇ CSV",
            pretty.to_csv(index=False).encode("utf-8"),
            file_name=f"anglers_{active}.csv",
            mime="text/csv", use_container_width=True, key="dl_anglers_csv")
    with c3:
        xlsx_buf = io.BytesIO()
        with pd.ExcelWriter(xlsx_buf, engine="openpyxl") as writer:
            pretty.to_excel(writer, sheet_name="All Anglers", index=False)
            # Also write one sheet per club for easy navigation
            for club, group in pretty.groupby("Club"):
                sheet = (club or "Unknown")[:31]  # Excel sheet name limit
                group.to_excel(writer, sheet_name=sheet, index=False)
        st.download_button(
            "⬇ Excel",
            xlsx_buf.getvalue(),
            file_name=f"anglers_{active}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True, key="dl_anglers_xlsx")
    st.dataframe(pretty, use_container_width=True, hide_index=True, height=300)


# ── Per-competition reports ───────────────────────────────────────────────
with st.container(border=True):
    section_label("Per-competition reports (7 files)")
    st.caption("Generates the 7 standard WCSAA report sheets for a single competition. "
               "Open in Excel → Save as PDF to print.")
    if not comps:
        st.warning("Add a competition first on the **Competitions** page.")
    else:
        comp = st.selectbox("Competition", comps, index=len(comps) - 1)
        if st.button("⚙ Generate 7 reports", type="primary"):
            with st.spinner("Generating reports…"):
                ok, log = run([sys.executable,
                               str(ROOT / "scripts" / "generate_reports.py"),
                               "--comp", comp, "--season", active])
            st.code(log or "(no output)")
            if ok:
                st.success(f"Reports written to `/reports/{active}/`.")
            else:
                st.error("Script returned an error — see output above.")

# ── Season summary downloads ───────────────────────────────────────────────
divider_label("Season summary — quick CSV exports")
scored  = load_catches_scored()
anglers = load_anglers()
comps_df = load_comps()
if scored.empty:
    empty_state("No catches recorded yet.", "📊")
else:
    cc = scored.copy()
    cc["weight_kg"] = pd.to_numeric(cc["weight_kg"], errors="coerce").fillna(0.0)
    cc["edible"]    = cc["edible"].fillna("").astype(str).str.upper()
    cc["valid"]     = cc["status"].fillna("").astype(str).str.lower().str.startswith("ok")
    cc = cc[cc["valid"]].copy()

    # Per-species
    species_summary = (cc.groupby("canonical_species")
                       .agg(catches=("weight_kg", "size"),
                            total_weight_kg=("weight_kg", "sum"),
                            heaviest_kg=("weight_kg", "max"),
                            avg_weight_kg=("weight_kg", "mean"))
                       .reset_index().rename(columns={"canonical_species": "Species"})
                       .sort_values("catches", ascending=False)
                       .round(3))

    # Per-venue (join comps → catches via comp_id)
    if not comps_df.empty:
        venue_map = dict(zip(comps_df["comp_id"].astype(str), comps_df["venue"]))
        cc["venue"] = cc["comp_id"].astype(str).map(venue_map).fillna("(unknown)")
        venue_summary = (cc.groupby("venue")
                         .agg(catches=("weight_kg", "size"),
                              total_weight_kg=("weight_kg", "sum"),
                              edibles=("edible", lambda s: (s == "Y").sum()),
                              non_edibles=("edible", lambda s: (s == "N").sum()))
                         .reset_index().rename(columns={"venue": "Venue"})
                         .sort_values("catches", ascending=False)
                         .round(3))
    else:
        venue_summary = pd.DataFrame()

    # Per-IC
    ic_summary = (cc.groupby("comp_id")
                  .agg(catches=("weight_kg", "size"),
                       total_weight_kg=("weight_kg", "sum"),
                       edibles=("edible", lambda s: (s == "Y").sum()),
                       non_edibles=("edible", lambda s: (s == "N").sum()),
                       unique_anglers=("wp_no", "nunique"))
                  .reset_index().rename(columns={"comp_id": "IC"})
                  .sort_values("IC")
                  .round(3))
    if not comps_df.empty:
        ic_summary["Venue"] = ic_summary["IC"].astype(str).map(venue_map).fillna("")
        ic_summary["Date"]  = ic_summary["IC"].astype(str).map(
            dict(zip(comps_df["comp_id"].astype(str), comps_df["date"]))).fillna("")
        ic_summary = ic_summary[["IC", "Date", "Venue", "catches", "total_weight_kg",
                                  "edibles", "non_edibles", "unique_anglers"]]

    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            section_label("By species")
            st.dataframe(species_summary, use_container_width=True, hide_index=True,
                         height=320)
            st.download_button(
                "⬇ Download species CSV",
                species_summary.to_csv(index=False).encode(),
                file_name=f"species_summary_{active}.csv",
                mime="text/csv", key="dl_species")
    with col2:
        with st.container(border=True):
            section_label("By venue")
            if venue_summary.empty:
                empty_state("No venues defined.", "📍")
            else:
                st.dataframe(venue_summary, use_container_width=True, hide_index=True,
                             height=320)
                st.download_button(
                    "⬇ Download venue CSV",
                    venue_summary.to_csv(index=False).encode(),
                    file_name=f"venue_summary_{active}.csv",
                    mime="text/csv", key="dl_venue")
    with col3:
        with st.container(border=True):
            section_label("Per IC")
            st.dataframe(ic_summary, use_container_width=True, hide_index=True,
                         height=320)
            st.download_button(
                "⬇ Download per-IC CSV",
                ic_summary.to_csv(index=False).encode(),
                file_name=f"per_ic_summary_{active}.csv",
                mime="text/csv", key="dl_per_ic")

    # ── Species composition per IC ─────────────────────────────────────
    section_label("Species composition per IC (counts + % share)")
    if not comps_df.empty:
        ic_label_map = {cid: f"IC {cid} ({d} · {v})"
                        for cid, d, v in zip(
                            comps_df["comp_id"].astype(str),
                            comps_df["date"],
                            comps_df["venue"])}
    else:
        ic_label_map = {cid: f"IC {cid}" for cid in cc["comp_id"].astype(str).unique()}
    cc["comp_label"] = cc["comp_id"].astype(str).map(ic_label_map)
    ordered_ic_labels = [ic_label_map[c] for c in
                          sorted(cc["comp_id"].astype(str).unique(),
                                 key=lambda x: (len(x), x))
                          if c in ic_label_map]

    # Counts
    counts = (cc.groupby(["canonical_species", "comp_label"]).size()
              .reset_index(name="Catches"))
    totals_per_ic = counts.groupby("comp_label")["Catches"].transform("sum")
    counts["% of IC"] = (counts["Catches"] / totals_per_ic * 100).round(1)
    pivot_n = counts.pivot_table(index="canonical_species", columns="comp_label",
                                  values="Catches", aggfunc="sum", observed=False).fillna(0)
    pivot_p = counts.pivot_table(index="canonical_species", columns="comp_label",
                                  values="% of IC", aggfunc="sum", observed=False).fillna(0)
    species_comp = pd.concat({"Catches": pivot_n, "% of IC": pivot_p}, axis=1)
    new_cols = []
    for ic in ordered_ic_labels:
        if ("Catches", ic) in species_comp.columns:
            new_cols += [("Catches", ic), ("% of IC", ic)]
    species_comp = species_comp[new_cols]
    species_comp[("Total", "Catches")] = pivot_n.sum(axis=1)
    species_comp = species_comp.sort_values(("Total", "Catches"), ascending=False)

    st.dataframe(species_comp, use_container_width=True, height=420)
    st.download_button(
        "⬇ Download species-composition CSV",
        species_comp.to_csv().encode(),
        file_name=f"species_composition_per_ic_{active}.csv",
        mime="text/csv", key="dl_species_comp")

# ── Grand Prix standings export ────────────────────────────────────────────
divider_label("Grand Prix standings (Trial)")
import grandprix as gpmod
gp_scored = load_catches_scored()
if gp_scored.empty:
    empty_state("No catches recorded yet.", "⚡")
else:
    gp_anglers = load_anglers()
    gp_comp_order = sorted(gp_scored["comp_id"].astype(str).unique().tolist())
    gc1, gc2, gc3 = st.columns(3)
    with gc1:
        r_drop = st.toggle("Best 7 of 8", value=False, key="rep_gp_drop")
    with gc2:
        r_pool = st.radio("Pool", ["Overall", "Per division"], horizontal=True,
                          key="rep_gp_pool")
    with gc3:
        r_fish = st.toggle("Add work-rate (+1/fish)", value=False, key="rep_gp_fish")
    pool = "division" if r_pool == "Per division" else "overall"
    gp_tbl = gpmod.gp_standings(gp_scored, gp_anglers, gp_comp_order,
                                drop_worst=r_drop, pool=pool, add_fish=r_fish)
    st.dataframe(gp_tbl, use_container_width=True, hide_index=True, height=320)

    rc1, rc2 = st.columns(2)
    with rc1:
        st.download_button(
            "⬇ Download GP standings CSV",
            gp_tbl.to_csv(index=False).encode(),
            file_name=f"grand_prix_standings_{active}.csv",
            mime="text/csv", key="rep_gp_csv")
    with rc2:
        gp_xlsx = io.BytesIO()
        with pd.ExcelWriter(gp_xlsx, engine="openpyxl") as writer:
            gp_tbl.to_excel(writer, sheet_name="GP Standings", index=False)
            # one per-IC GP sheet too
            for c in gp_comp_order:
                t = gpmod.per_ic_table(gp_scored, gp_anglers, c, pool=pool, add_fish=r_fish)
                if not t.empty:
                    t.to_excel(writer, sheet_name=f"IC{c} GP"[:31], index=False)
        st.download_button(
            "⬇ Download GP workbook (XLSX)",
            gp_xlsx.getvalue(),
            file_name=f"grand_prix_{active}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="rep_gp_xlsx")

# ── Master tracker ────────────────────────────────────────────────────────
divider_label("Master league tracker")
with st.container(border=True):
    section_label("Single workbook (all clubs + standings)")
    st.caption("Dashboard · Club Standings · Individual Standings · one sheet per club · Notes. "
               "Saved to your Desktop\\League folder and available for download below.")
    if st.button("⚙ Build tracker", type="primary", key="build_tracker"):
        with st.spinner("Building tracker…"):
            ok, log = run([sys.executable,
                           str(ROOT / "scripts" / "build_tracker.py")])
        st.code(log or "(no output)")
        if ok:
            st.success("Tracker built successfully.")
        else:
            st.error("Script returned an error — see output above.")

# ── Available files ───────────────────────────────────────────────────────
divider_label("Available files")
if REPORTS_DIR.exists():
    files = sorted(REPORTS_DIR.glob("*.xlsx"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        st.info("No reports generated yet.")
    else:
        kpi_row([{"icon": "📄", "label": "Report files", "value": len(files)}])
        for f in files:
            c1, c2 = st.columns([5, 1])
            c1.write(f"**{f.name}** · {f.stat().st_size / 1024:.0f} KB")
            c2.download_button(
                "⬇ Download", f.read_bytes(),
                file_name=f.name, key=f"dl_{f.name}",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.info(f"Reports folder `reports/{active}/` does not exist yet.")

# ── Desktop tracker ───────────────────────────────────────────────────────
tracker_name = f"4OAC_League_Tracker_{active}.xlsx"
desktop_candidates = [
    Path.home() / "OneDrive - Africa Cricket Development (Pty) Ltd"
    / "Desktop" / "League" / tracker_name,
    Path.home() / "OneDrive" / "Desktop" / "League" / tracker_name,
    Path.home() / "Desktop" / "League" / tracker_name,
]
for p in desktop_candidates:
    if p.exists():
        divider_label("Tracker on Desktop")
        st.caption(str(p))
        st.download_button(
            "⬇ Download tracker", p.read_bytes(),
            file_name=p.name, key="dl_tracker",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        break
