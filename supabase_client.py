"""
Supabase client singleton for the WCSAA Scoring app.
Initialised once per Streamlit server process via st.cache_resource.

Secrets required in .streamlit/secrets.toml (local) or Streamlit Cloud:
    SUPABASE_URL = "https://<project-ref>.supabase.co"
    SUPABASE_KEY = "<service_role_key>"

Note: Use the service_role key (sb_secret_...) not the anon/publishable key.
Service_role bypasses RLS — safe here because Streamlit is server-side only.
If RLS is disabled (the default for this app), the anon key also works.
"""
from __future__ import annotations

import streamlit as st
from supabase import Client, create_client


@st.cache_resource(show_spinner=False)
def get_supabase() -> Client:
    """Return a cached Supabase client. Called on every page — fast after first load."""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except KeyError as exc:
        st.error(
            f"🔴 **Supabase not configured** — missing secret: `{exc}`. "
            "Add `SUPABASE_URL` and `SUPABASE_KEY` to your Streamlit secrets "
            "(Settings → Secrets in Streamlit Cloud, or `.streamlit/secrets.toml` locally)."
        )
        st.stop()
    return create_client(url, key)
