"""Shared helpers for the WCSAA League Streamlit app.

Season-aware data layer backed by Supabase PostgreSQL (via database.py).
All CSV read/write has been replaced with Supabase calls — this module retains:
  - Scoring engine wrapper (rescore_all, load_catches_scored, points_for)
  - Season create/delete (validation logic lives here; DB I/O in database.py)
  - Logo management (local filesystem; bundled logos in git persist across restarts)
  - UI helpers (filters, sidebar, highlight)
  - Constants and label helpers
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT    = Path(__file__).resolve().parent
DATA    = ROOT / "data"
SCRIPTS = ROOT / "scripts"
LOGOS_DIR = DATA / "logos"
LOGO_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")

sys.path.insert(0, str(SCRIPTS))
from scoring import Scorer  # noqa: E402

# ── Re-export database functions so existing page imports still work ───────────
from database import (          # noqa: F401 (re-exported for pages)
    list_seasons,
    get_active_season,
    set_active_season,
    load_anglers,
    save_anglers,
    load_comps,
    save_comps,
    load_catches_raw,
    load_team_assignments,
    save_team_assignments,
    load_trophy_nominees,
    save_trophy_nominees,
    clear_catches,
    clear_all_season_data,
)

# ── Scoring constants ──────────────────────────────────────────────────────────
EDIBLE_PTS_PER_KG    = 4.0
NON_EDIBLE_PTS_PER_KG = 1.0
EDIBLE_MIN_KG        = 0.5      # edible catches under this threshold score 0
NON_EDIBLE_MIN_KG    = 1.0      # non-edible catches under this threshold score 0
FLAT_PT_PATTERNS     = ("gurnard", "catfish")   # flat 1 pt per fish (Barbel aliased to Catfish)
FLAT_PT_VALUE        = 1.0

# ── Column schemas ────────────────────────────────────────────────────────────
DEFAULT_ANGLER_COLS = ["wp_no", "sasaa_no", "first_name", "surname", "club",
                       "sub_team", "league_division", "league_code"]
DEFAULT_COMP_COLS   = ["comp_id", "date", "venue"]
DEFAULT_CATCH_COLS  = ["comp_id", "wp_no", "species_raw", "length_cm"]

# ── Club / division constants ─────────────────────────────────────────────────
CLUBS = ["TWO OCEANS", "FALSEBAY", "TYGERBERG", "BLUE RAY",
         "FOUR OCEANS", "GOODWOOD", "POLICE"]
SUB_TEAMS = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
DIVISIONS = {
    "G": "GrandMasters",
    "J": "Juniors",
    "K": "Kids",
    "L": "Ladies",
    "M": "Masters",
    "S": "Seniors",
}
DIVISION_CODES  = list(DIVISIONS.keys())
DIVISION_LABELS = [f"{c} — {DIVISIONS[c]}" for c in DIVISION_CODES]


def floor2(x: float) -> float:
    """Round DOWN to 2 decimal places."""
    return math.floor(float(x) * 100) / 100.0


def division_label(code: str) -> str:
    code = (code or "").strip().upper()
    return f"{code} — {DIVISIONS[code]}" if code in DIVISIONS else ""


def division_code(label: str) -> str:
    if not label:
        return ""
    return label.split(" — ", 1)[0].strip().upper()


# ── Season creation / deletion (validation here; DB I/O in database.py) ───────

def create_season(season: str, *, carry_anglers_from: str | None) -> str:
    from database import create_season as _db_create
    season = season.strip()
    if not season:
        raise ValueError("Season label cannot be empty")
    if not re.match(r"^[A-Za-z0-9_\-]+$", season):
        raise ValueError("Use letters, numbers, '-' or '_' only (e.g. 2026-27)")
    if season in list_seasons():
        raise ValueError(f"Season '{season}' already exists")
    return _db_create(season, carry_anglers_from=carry_anglers_from)


def delete_season(season: str) -> None:
    from database import delete_season as _db_delete
    was_active = (get_active_season() == season)
    _db_delete(season)
    if was_active:
        remaining = list_seasons()
        if remaining:
            set_active_season(remaining[0])


# ── Scoring engine ─────────────────────────────────────────────────────────────

def is_flat_pt_species(canonical: str | None) -> bool:
    if not canonical:
        return False
    n = str(canonical).strip().lower()
    return any(n.startswith(p) for p in FLAT_PT_PATTERNS)


def points_for(weight_kg: float, edible: str, canonical: str | None = None) -> float:
    """Compute points for a single catch.

    Rules (in order of precedence):
      1. Gurnards / Catfish (Barbel) → flat 1 pt per fish.
      2. Edible < 0.5 kg → 0 pts.
      3. Non-edible < 1 kg → 0 pts.
      4. Edible: weight × 4 pts/kg, floored to 2 dp.
      5. Non-edible: weight × 1 pt/kg, floored to 2 dp.
    """
    if is_flat_pt_species(canonical):
        return FLAT_PT_VALUE
    w = float(weight_kg or 0.0)
    is_edible = str(edible).upper() == "Y"
    if is_edible and w < EDIBLE_MIN_KG:
        return 0.00
    if not is_edible and w < NON_EDIBLE_MIN_KG:
        return 0.00
    rate = EDIBLE_PTS_PER_KG if is_edible else NON_EDIBLE_PTS_PER_KG
    return floor2(w * rate)


@st.cache_resource
def get_scorer() -> Scorer:
    """Cached species scorer (reads data/species_master.csv + species_aliases.json)."""
    return Scorer()


def species_choices() -> list[str]:
    s = get_scorer()
    return sorted(s.aliases.keys()) + sorted(s.species.index.tolist())


# ── Catches: validated save + rescore ─────────────────────────────────────────

def save_catches_raw(df: pd.DataFrame) -> None:
    """Validate raw catches, persist to Supabase, then trigger a full rescore."""
    from database import db_save_catches_raw as _write
    df = df.copy()
    for c in DEFAULT_CATCH_COLS:
        if c not in df.columns:
            df[c] = ""
    df = df[DEFAULT_CATCH_COLS]
    df["wp_no"]       = df["wp_no"].astype(str).str.strip()
    df["comp_id"]     = df["comp_id"].astype(str).str.strip()
    df["species_raw"] = df["species_raw"].astype(str).str.strip()
    df = df[
        (df["wp_no"] != "") & (df["comp_id"] != "") & (df["species_raw"] != "")
    ].reset_index(drop=True)
    _write(df)
    rescore_all()


def rescore_all() -> pd.DataFrame:
    """Score all raw catches for the active season and persist to catches_scored."""
    from database import db_save_catches_scored as _save
    scorer = get_scorer()
    raw    = load_catches_raw()
    rows   = []
    for _, r in raw.iterrows():
        try:
            L = float(r["length_cm"]) if r["length_cm"] not in ("", None, "nan") else None
        except (TypeError, ValueError):
            L = None
        res = scorer.score(r["species_raw"], L)
        rows.append({
            "comp_id":          r["comp_id"],
            "wp_no":            r["wp_no"],
            "species_raw":      r["species_raw"],
            "canonical_species": res.canonical_name,
            "length_cm":        L,
            "weight_kg":        floor2(res.weight_kg),
            "edible":           res.edible,
            "status":           res.note,
        })
    df = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["comp_id", "wp_no", "species_raw", "canonical_species",
                 "length_cm", "weight_kg", "edible", "status"]
    )
    _save(df)
    return df


def load_catches_scored() -> pd.DataFrame:
    """Load scored catches, computing points on the fly.

    If the scored table is empty but raw catches exist, triggers a rescore first.
    Points are not stored in DB — always computed from weight_kg + edible.
    """
    from database import load_catches_scored_raw as _load
    df = _load()
    if df.empty:
        raw = load_catches_raw()
        if not raw.empty:
            df = rescore_all()
        else:
            empty = pd.DataFrame(
                columns=["comp_id", "wp_no", "species_raw", "canonical_species",
                         "length_cm", "weight_kg", "edible", "status"]
            )
            empty["points"] = pd.Series(dtype=float)
            return empty
    df = df.copy()
    df["wp_no"]   = df["wp_no"].astype(str).str.strip()
    df["comp_id"] = df["comp_id"].astype(str).str.strip()
    df["points"]  = df.apply(
        lambda r: points_for(r["weight_kg"], r["edible"], r.get("canonical_species")),
        axis=1,
    )
    return df


# ── Convenience helpers ────────────────────────────────────────────────────────

def comp_options() -> list[str]:
    return load_comps()["comp_id"].dropna().astype(str).str.strip().tolist()


def angler_options() -> list[str]:
    a = load_anglers()
    return [f"{r.wp_no} — {r.first_name} {r.surname}" for r in a.itertuples()]


def parse_wp_from_label(label: str) -> str:
    return label.split(" — ", 1)[0].strip() if label else ""


# ── Sub-team resolution ────────────────────────────────────────────────────────

def resolve_sub_team(catches: pd.DataFrame, anglers: pd.DataFrame) -> pd.DataFrame:
    """Add 'sub_team' column to catches — per-comp assignment overrides angler default."""
    out = catches.copy()
    ta  = load_team_assignments()
    if not ta.empty:
        out = out.merge(
            ta.rename(columns={"sub_team": "sub_team_assigned"}),
            on=["comp_id", "wp_no"], how="left",
        )
    else:
        out["sub_team_assigned"] = ""
    out = out.merge(
        anglers[["wp_no", "sub_team"]].rename(columns={"sub_team": "sub_team_default"}),
        on="wp_no", how="left",
    )
    assigned = out["sub_team_assigned"].fillna("").astype(str).str.upper().str.strip()
    default  = out["sub_team_default"].fillna("").astype(str).str.upper().str.strip()
    out["sub_team"] = assigned.where(assigned != "", default)
    return out.drop(columns=["sub_team_assigned", "sub_team_default"], errors="ignore")


# ── Logo management ────────────────────────────────────────────────────────────
# Logos are read from local filesystem (data/logos/).
# Bundled club logos in git persist across Streamlit Cloud restarts.
# Logos uploaded via the UI survive until the next container restart —
# for permanent uploads, commit the file to git or add Supabase Storage (future).

def safe_slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").strip().lower()).strip("_")


def _logo_search(slug: str) -> Path | None:
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    for ext in LOGO_EXTS:
        p = LOGOS_DIR / f"{slug}{ext}"
        if p.exists() and p.is_file() and p.stat().st_size > 0:
            return p
    return None


def get_logo_bytes(key: str) -> bytes | None:
    p = _logo_search(safe_slug(key))
    return p.read_bytes() if p else None


def save_logo(key: str, uploaded_file) -> Path:
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    slug = safe_slug(key)
    for ext in LOGO_EXTS:
        old = LOGOS_DIR / f"{slug}{ext}"
        if old.exists():
            old.unlink()
    suffix = Path(uploaded_file.name).suffix.lower() or ".png"
    if suffix not in LOGO_EXTS:
        suffix = ".png"
    target = LOGOS_DIR / f"{slug}{suffix}"
    target.write_bytes(uploaded_file.getbuffer())
    return target


def remove_logo(key: str) -> None:
    slug = safe_slug(key)
    for ext in LOGO_EXTS:
        p = LOGOS_DIR / f"{slug}{ext}"
        if p.exists():
            p.unlink()


def manage_logo(key: str, *, label: str = "Logo", width: int = 180,
                placeholder: str = "No logo uploaded yet.") -> None:
    """Render a compact upload/preview/remove block for the given logo key."""
    img = get_logo_bytes(key)
    c1, c2 = st.columns([1, 3])
    with c1:
        if img:
            st.image(img, width=width)
        else:
            st.info(placeholder)
    with c2:
        up = st.file_uploader(label, type=[e[1:] for e in LOGO_EXTS],
                              key=f"_upl_{safe_slug(key)}")
        if up is not None:
            save_logo(key, up)
            st.success("Logo saved.")
            st.rerun()
        if img and st.button("Remove logo", key=f"_rm_{safe_slug(key)}"):
            remove_logo(key)
            st.success("Logo removed.")
            st.rerun()


# ── Global filters ────────────────────────────────────────────────────────────

def render_global_filters(catches: pd.DataFrame, anglers: pd.DataFrame) -> dict:
    """Render Comp / Club / Division multiselects in the sidebar."""
    ss = st.session_state
    ss.setdefault("gf_comp", [])
    ss.setdefault("gf_club", [])
    ss.setdefault("gf_div", [])

    comp_opts = sorted(catches["comp_id"].astype(str).unique().tolist()) if len(catches) else []
    club_opts = sorted([c for c in anglers.get("club", pd.Series(dtype=str)).unique() if c])
    div_codes = list(DIVISIONS.keys())

    with st.sidebar:
        st.markdown("### Filters")
        ss.gf_comp = st.multiselect(
            "Competition", comp_opts,
            default=[c for c in ss.gf_comp if c in comp_opts],
            key="_gf_comp_w",
        )
        ss.gf_club = st.multiselect(
            "Club", club_opts,
            default=[c for c in ss.gf_club if c in club_opts],
            key="_gf_club_w",
        )
        ss.gf_div = st.multiselect(
            "Division", div_codes,
            default=[d for d in ss.gf_div if d in div_codes],
            format_func=lambda c: f"{c} — {DIVISIONS.get(c, '')}",
            key="_gf_div_w",
        )
        if any([ss.gf_comp, ss.gf_club, ss.gf_div]):
            if st.button("✖ Clear filters", use_container_width=True, key="_gf_clear"):
                ss.gf_comp = []
                ss.gf_club = []
                ss.gf_div  = []
                st.rerun()
    return {"comp": ss.gf_comp, "club": ss.gf_club, "division": ss.gf_div}


def apply_filters(catches: pd.DataFrame, anglers: pd.DataFrame,
                  filters: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (filtered_catches, filtered_anglers) narrowed by the same filters."""
    a = anglers.copy()
    if filters.get("club"):
        a = a[a["club"].isin(filters["club"])]
    if filters.get("division"):
        a = a[a["league_code"].isin(filters["division"])]
    keep_wp = set(a["wp_no"]) if not a.empty else set()
    c = catches.copy()
    if filters.get("comp"):
        c = c[c["comp_id"].isin(filters["comp"])]
    if filters.get("club") or filters.get("division"):
        c = c[c["wp_no"].isin(keep_wp)]
    return c.reset_index(drop=True), a.reset_index(drop=True)


def highlight_leader(df: pd.DataFrame):
    """Pandas Styler that highlights the first row (gold) — leader/winner row."""
    from theme import load_theme
    t  = load_theme()
    bg = t.get("leader_highlight", "#FFF5CC")

    def _row(_):
        styles = pd.DataFrame("", index=df.index, columns=df.columns)
        if len(df):
            styles.iloc[0, :] = f"background-color: {bg}; font-weight: 600;"
        return styles
    return df.style.apply(_row, axis=None)


def render_season_sidebar() -> str:
    """Sidebar widget shown on every page — switches the active season and injects CSS."""
    from theme import inject_css
    from version import version_footer_html
    inject_css()
    active = get_active_season()
    with st.sidebar:
        st.markdown("### Season")
        seasons = list_seasons()
        idx  = seasons.index(active) if active in seasons else 0
        pick = st.selectbox("Active", seasons, index=idx, key="_season_sidebar")
        if pick != active:
            set_active_season(pick)
            st.rerun()
        st.caption("Switch / create / clear on **Settings**.")
        st.markdown(version_footer_html(), unsafe_allow_html=True)
    return pick
