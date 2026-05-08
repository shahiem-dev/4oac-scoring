"""Generate printable XLSX reports and the master tracker workbook."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import streamlit as st

from app_lib import ROOT, comp_options, render_season_sidebar
from ui import divider_label, kpi_row, page_header, section_label

st.set_page_config(page_title="Reports · WCSAA League", page_icon="📑", layout="wide")
active      = render_season_sidebar()
REPORTS_DIR = ROOT / "reports" / active
page_header("Reports & Exports", "Generate XLSX reports and the master tracker workbook",
            "📑", active)


def run(cmd: list[str]) -> tuple[bool, str]:
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return res.returncode == 0, (res.stdout + res.stderr).strip()


comps = comp_options()

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
