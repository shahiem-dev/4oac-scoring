"""Reusable UI display components for the WCSAA scoring app.

All functions render via st.markdown(unsafe_allow_html=True).
The matching CSS classes are injected by theme.py → inject_css().
No logic or data access here — purely presentation.
"""
from __future__ import annotations

import html as _html

import streamlit as st


# ── Page header ────────────────────────────────────────────────────────────

def page_header(title: str, subtitle: str = "", icon: str = "",
                season: str = "") -> None:
    """Gradient header strip at the top of every page."""
    icon_html  = f'<span class="wph-icon">{icon}</span>' if icon else ""
    sub_html   = (f'<div class="wph-sub">{_html.escape(subtitle)}</div>'
                  if subtitle else "")
    sea_html   = (f'<span class="wph-season">📅 {_html.escape(season)}</span>'
                  if season else "")
    st.markdown(
        f'<div class="wcsaa-page-header">'
        f'  {icon_html}'
        f'  <div class="wph-body">'
        f'    <div class="wph-title">{_html.escape(title)}</div>'
        f'    {sub_html}'
        f'  </div>'
        f'  {sea_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── KPI metric row ─────────────────────────────────────────────────────────

def kpi_row(metrics: list[dict]) -> None:
    """Render a horizontal row of KPI tiles.

    Each dict accepts: label (str), value (str|int|float), icon (emoji str),
    sub (secondary line str).
    """
    cards = ""
    for m in metrics:
        icon  = m.get("icon", "")
        value = m.get("value", "—")
        label = _html.escape(str(m.get("label", "")))
        sub   = m.get("sub", "")
        icon_html = f'<div class="kpi-icon">{icon}</div>' if icon else ""
        sub_html  = (f'<div class="kpi-sub">{_html.escape(str(sub))}</div>'
                     if sub else "")
        cards += (
            f'<div class="wcsaa-kpi-card">'
            f'  {icon_html}'
            f'  <div class="kpi-value">{_html.escape(str(value))}</div>'
            f'  <div class="kpi-label">{label}</div>'
            f'  {sub_html}'
            f'</div>'
        )
    st.markdown(f'<div class="wcsaa-kpi-row">{cards}</div>',
                unsafe_allow_html=True)


# ── Leader highlight banner ────────────────────────────────────────────────

def leader_banner(medal: str, name: str, detail: str = "",
                  pts: str = "") -> None:
    """Gold-accent banner shown below a trophy / standings table."""
    pts_html = (f'<div class="lb-pts">{_html.escape(pts)}</div>'
                if pts else "")
    st.markdown(
        f'<div class="wcsaa-leader-banner">'
        f'  <div class="lb-medal">{medal}</div>'
        f'  <div class="lb-body">'
        f'    <div class="lb-name">{_html.escape(name)}</div>'
        f'    <div class="lb-detail">{_html.escape(detail)}</div>'
        f'  </div>'
        f'  {pts_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Section label & divider ────────────────────────────────────────────────

def section_label(text: str) -> None:
    """Small uppercase label with accent underline — use instead of subheader."""
    st.markdown(
        f'<div class="wcsaa-section-label">{_html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


def divider_label(text: str) -> None:
    """Horizontal rule with a centre-aligned text label."""
    st.markdown(
        f'<div class="wcsaa-divider"><span>{_html.escape(text)}</span></div>',
        unsafe_allow_html=True,
    )


# ── Empty state ────────────────────────────────────────────────────────────

def empty_state(message: str = "No data yet.", icon: str = "🎣") -> None:
    """Centred empty-state placeholder with icon."""
    st.markdown(
        f'<div class="wcsaa-empty">'
        f'  <div class="ee-icon">{icon}</div>'
        f'  <p>{_html.escape(message)}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Status pill ────────────────────────────────────────────────────────────

def status_pill(status: str) -> str:
    """Return an inline HTML status badge string (not rendered — embed in markdown)."""
    s = str(status).lower()
    if s.startswith("ok"):
        cls, txt = "wcsaa-pill-ok",   f"✓ {status}"
    elif "unknown" in s or "error" in s:
        cls, txt = "wcsaa-pill-err",  f"✗ {status}"
    else:
        cls, txt = "wcsaa-pill-warn", f"⚠ {status}"
    return f'<span class="wcsaa-pill {cls}">{_html.escape(txt)}</span>'


# ── Info card (inline HTML block) ─────────────────────────────────────────

def info_card(body: str, *, title: str = "", icon: str = "") -> None:
    """A simple bordered info card using plain HTML."""
    hdr = ""
    if title:
        hdr = (f'<div class="wcsaa-card-header">'
               f'  {icon + " " if icon else ""}'
               f'  {_html.escape(title)}'
               f'</div>')
    st.markdown(
        f'<div class="wcsaa-card">{hdr}<div>{body}</div></div>',
        unsafe_allow_html=True,
    )
