"""Single source of truth for app version and runtime environment.

Version scheme: MAJOR.MINOR.PATCH
  MAJOR — breaking change to data schema or scoring rules
  MINOR — new feature or page
  PATCH — bug fix, UI tweak, data correction

Environment is read from Streamlit secrets (APP_ENV key) so the same
codebase can be deployed as staging or production simply by changing the
secret — no code changes needed.

Streamlit Cloud — Secrets tab:
    APP_ENV = "staging"       # staging app
    APP_ENV = "production"    # production app (or omit entirely)
"""
from __future__ import annotations

import os

# ── Version ──────────────────────────────────────────────────────────────
__version__   = "1.2.0"
__build_date__ = "2026-06-01"

# ── Environment detection ─────────────────────────────────────────────────
def _read_env() -> str:
    """Return 'staging' or 'production'. Never raises."""
    try:
        import streamlit as st
        return str(st.secrets.get("APP_ENV", os.getenv("APP_ENV", "production"))).lower()
    except Exception:
        return os.getenv("APP_ENV", "production").lower()


APP_ENV    = _read_env()
IS_STAGING = APP_ENV == "staging"


# ── Sidebar badge HTML ────────────────────────────────────────────────────
def env_badge_html() -> str:
    """Return an HTML badge string for display in the sidebar."""
    if IS_STAGING:
        return (
            '<span style="background:#F59E0B;color:#fff;font-size:0.65rem;'
            'font-weight:700;padding:2px 8px;border-radius:10px;'
            'text-transform:uppercase;letter-spacing:0.06em;">⚗ Staging</span>'
        )
    return (
        '<span style="background:#16A34A;color:#fff;font-size:0.65rem;'
        'font-weight:700;padding:2px 8px;border-radius:10px;'
        'text-transform:uppercase;letter-spacing:0.06em;">✓ Production</span>'
    )


def version_footer_html() -> str:
    """Return the full sidebar footer HTML block."""
    badge = env_badge_html()
    return (
        f'<div style="margin-top:1.5rem;padding-top:0.75rem;'
        f'border-top:1px solid rgba(255,255,255,0.12);'
        f'font-size:0.72rem;color:rgba(255,255,255,0.45);line-height:1.7;">'
        f'  {badge}<br>'
        f'  <span>v{__version__}</span>'
        f'  <span style="margin-left:6px;opacity:0.6;">{__build_date__}</span>'
        f'</div>'
    )
