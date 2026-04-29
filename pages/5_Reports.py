"""Generate the 7 printable reports + the master tracker workbook."""
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import streamlit as st

from app_lib import ROOT, comp_options, render_season_sidebar

st.set_page_config(page_title="Reports · WCSAA League", page_icon="📑", layout="wide")
active = render_season_sidebar()
st.title(f"📑 Reports — {active}")
st.caption("Generate printable XLSX outputs. Open in Excel and 'Save as PDF' for printing.")

REPORTS_DIR = ROOT / "reports" / active


def run(cmd: list[str]) -> tuple[bool, str]:
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return res.returncode == 0, (res.stdout + res.stderr).strip()


comps = comp_options()

st.subheader("Per-competition reports (7 files)")
if not comps:
    st.warning("Add a competition first.")
else:
    comp = st.selectbox("Competition", comps, index=len(comps) - 1)
    if st.button("Generate the 7 reports", type="primary"):
        ok, log = run([sys.executable, str(ROOT / "scripts" / "generate_reports.py"),
                       "--comp", comp, "--season", active])
        st.code(log or "(no output)")
        if ok:
            st.success("Reports written to /reports.")

st.divider()

st.subheader("Master league tracker (single workbook)")
st.caption("Dashboard + Club Standings + Individual Standings + one sheet per club + Notes. Saved to your Desktop\\League folder and made available below.")
if st.button("Build tracker", type="primary", key="build_tracker"):
    ok, log = run([sys.executable, str(ROOT / "scripts" / "build_tracker.py")])
    st.code(log or "(no output)")

st.divider()

st.subheader("Available files")
if REPORTS_DIR.exists():
    files = sorted(REPORTS_DIR.glob("*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        st.info("No reports generated yet.")
    for f in files:
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{f.name}**  ·  {f.stat().st_size / 1024:.0f} KB")
        c2.download_button("⬇ Download", f.read_bytes(), file_name=f.name,
                           key=f"dl_{f.name}",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Tracker file lives on Desktop, named per season
tracker_name = f"4OAC_League_Tracker_{active}.xlsx"
desktop_candidates = [
    Path.home() / "OneDrive - Africa Cricket Development (Pty) Ltd" / "Desktop" / "League" / tracker_name,
    Path.home() / "OneDrive" / "Desktop" / "League" / tracker_name,
    Path.home() / "Desktop" / "League" / tracker_name,
]
for p in desktop_candidates:
    if p.exists():
        st.divider()
        st.subheader("Tracker on Desktop")
        st.caption(str(p))
        st.download_button("⬇ Download tracker", p.read_bytes(),
                           file_name=p.name, key="dl_tracker",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        break
