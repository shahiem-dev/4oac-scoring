"""
Supabase database layer for the WCSAA Scoring app.

Every public function mirrors its CSV counterpart in app_lib.py, returning
pd.DataFrame objects with identical column schemas so page code needs no changes.

Design principles (borrowed from 4OAC Winter League):
  - get_supabase() is cached via @st.cache_resource — one connection per process
  - Reads  → table.select("*").eq("season_id", season).execute()
  - Writes → delete-then-insert for bulk season data (matches CSV overwrite behaviour)
  - Upserts → table.upsert(rows, on_conflict="pk_col").execute() for keyed tables
  - Column schemas defined as constants — single source of truth
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from supabase_client import get_supabase

# ── Column schema constants ───────────────────────────────────────────────────

ANGLER_COLS   = ["wp_no", "sasaa_no", "first_name", "surname", "club",
                 "sub_team", "league_division", "league_code"]
COMP_COLS     = ["comp_id", "date", "venue"]
RAW_COLS      = ["comp_id", "wp_no", "species_raw", "length_cm"]
SCORED_COLS   = ["comp_id", "wp_no", "species_raw", "canonical_species",
                 "length_cm", "weight_kg", "edible", "status"]
TEAM_COLS     = ["comp_id", "wp_no", "sub_team"]
NOMINEE_COLS  = ["trophy", "comp_id", "club", "wp_no"]

# ── Internal helpers ──────────────────────────────────────────────────────────

def _fetch_all(table: str, cols: list[str], season: str) -> list[dict[str, Any]]:
    """Fetch every row for a season, paginating past Supabase's 1000-row cap."""
    sb = get_supabase()
    page = 0
    out: list[dict[str, Any]] = []
    while True:
        res = (sb.table(table)
                 .select(",".join(cols))
                 .eq("season_id", season)
                 .range(page * 1000, (page + 1) * 1000 - 1)
                 .execute())
        data = res.data or []
        out.extend(data)
        if len(data) < 1000:
            break
        page += 1
    return out


def _to_df(rows: list[dict[str, Any]], cols: list[str]) -> pd.DataFrame:
    """Convert Supabase response rows → DataFrame with guaranteed column set."""
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols].fillna("")


def _rows(df: pd.DataFrame, cols: list[str], season_id: str) -> list[dict[str, Any]]:
    """Coerce DataFrame → list of dicts with season_id injected, ready for Supabase insert."""
    tmp = df.copy()
    for c in cols:
        if c not in tmp.columns:
            tmp[c] = ""
    tmp = tmp[cols].fillna("").astype(str)
    tmp["season_id"] = season_id
    return tmp.to_dict(orient="records")


# ── Season management ─────────────────────────────────────────────────────────

def list_seasons() -> list[str]:
    """Return all season IDs sorted alphabetically."""
    res = get_supabase().table("seasons").select("season_id").order("season_id").execute()
    return [r["season_id"] for r in res.data]


def get_active_season() -> str:
    """Return the currently active season ID.

    Falls back to the first available season, then creates '2025-26' if none exist.
    """
    res = get_supabase().table("seasons").select("season_id").eq("is_active", True).limit(1).execute()
    if res.data:
        return res.data[0]["season_id"]
    # Fallback: activate first available season
    seasons = list_seasons()
    if seasons:
        set_active_season(seasons[0])
        return seasons[0]
    # No seasons at all — bootstrap with default
    create_season("2025-26", carry_anglers_from=None)
    set_active_season("2025-26")
    return "2025-26"


def set_active_season(season: str) -> None:
    """Mark season as active; deactivates all others atomically."""
    sb = get_supabase()
    # Deactivate all seasons
    sb.table("seasons").update({"is_active": False}).neq("season_id", "___never___").execute()
    # Activate the target season
    sb.table("seasons").update({"is_active": True}).eq("season_id", season).execute()


def create_season(season: str, *, carry_anglers_from: str | None) -> str:
    """Insert a new season row and optionally copy anglers from another season."""
    sb = get_supabase()
    sb.table("seasons").upsert(
        {"season_id": season, "is_active": False},
        on_conflict="season_id",
    ).execute()
    if carry_anglers_from:
        res = sb.table("anglers").select("*").eq("season_id", carry_anglers_from).execute()
        if res.data:
            new_rows = [
                {**{k: v for k, v in row.items() if k in ANGLER_COLS}, "season_id": season}
                for row in res.data
            ]
            if new_rows:
                sb.table("anglers").upsert(new_rows, on_conflict="wp_no,season_id").execute()
    return season


def delete_season(season: str) -> None:
    """Delete a season and all its data via CASCADE."""
    get_supabase().table("seasons").delete().eq("season_id", season).execute()


# ── Clear helpers ─────────────────────────────────────────────────────────────

def clear_catches(season: str | None = None) -> None:
    """Delete all catches and team assignments for the given season."""
    s = season or get_active_season()
    sb = get_supabase()
    sb.table("catches_raw").delete().eq("season_id", s).execute()
    sb.table("catches_scored").delete().eq("season_id", s).execute()
    sb.table("team_assignments").delete().eq("season_id", s).execute()


def clear_all_season_data(season: str | None = None) -> None:
    """Wipe anglers, competitions and catches for the season. Species master untouched."""
    s = season or get_active_season()
    sb = get_supabase()
    sb.table("anglers").delete().eq("season_id", s).execute()
    sb.table("competitions").delete().eq("season_id", s).execute()
    clear_catches(s)


# ── Anglers ───────────────────────────────────────────────────────────────────

def load_anglers() -> pd.DataFrame:
    season = get_active_season()
    res = (get_supabase()
           .table("anglers")
           .select(",".join(ANGLER_COLS))
           .eq("season_id", season)
           .order("surname")
           .execute())
    df = _to_df(res.data, ANGLER_COLS)
    df["wp_no"] = df["wp_no"].str.strip()
    return df


def save_anglers(df: pd.DataFrame) -> None:
    """Replace all anglers for the active season."""
    season = get_active_season()
    sb = get_supabase()
    # Validate
    df = df.copy()
    df["wp_no"] = df["wp_no"].astype(str).str.strip()
    df = df[df["wp_no"] != ""].reset_index(drop=True)
    # Replace
    sb.table("anglers").delete().eq("season_id", season).execute()
    if not df.empty:
        rows = _rows(df, ANGLER_COLS, season)
        sb.table("anglers").insert(rows).execute()


# ── Competitions ──────────────────────────────────────────────────────────────

def load_comps() -> pd.DataFrame:
    season = get_active_season()
    res = (get_supabase()
           .table("competitions")
           .select(",".join(COMP_COLS))
           .eq("season_id", season)
           .execute())
    return _to_df(res.data, COMP_COLS)


def save_comps(df: pd.DataFrame) -> None:
    """Replace all competitions for the active season."""
    season = get_active_season()
    sb = get_supabase()
    df = df.copy()
    df["comp_id"] = df["comp_id"].astype(str).str.strip()
    df = df[df["comp_id"] != ""].reset_index(drop=True)
    sb.table("competitions").delete().eq("season_id", season).execute()
    if not df.empty:
        rows = _rows(df, COMP_COLS, season)
        sb.table("competitions").insert(rows).execute()


# ── Catches raw ───────────────────────────────────────────────────────────────

def load_catches_raw() -> pd.DataFrame:
    season = get_active_season()
    rows   = _fetch_all("catches_raw", RAW_COLS, season)
    df = _to_df(rows, RAW_COLS)
    df["wp_no"]   = df["wp_no"].str.strip()
    df["comp_id"] = df["comp_id"].str.strip()
    return df


def db_save_catches_raw(df: pd.DataFrame) -> None:
    """Replace all raw catches for the active season (called by app_lib.save_catches_raw)."""
    season = get_active_season()
    sb = get_supabase()
    sb.table("catches_raw").delete().eq("season_id", season).execute()
    if not df.empty:
        rows = _rows(df, RAW_COLS, season)
        sb.table("catches_raw").insert(rows).execute()


# ── Catches scored ────────────────────────────────────────────────────────────

def load_catches_scored_raw() -> pd.DataFrame:
    """Return scored catches from DB (without computing points column).

    app_lib.load_catches_scored() wraps this and adds the points computation.
    """
    season = get_active_season()
    rows   = _fetch_all("catches_scored", SCORED_COLS, season)
    df = _to_df(rows, SCORED_COLS)
    if df.empty:
        return df
    df["wp_no"]     = df["wp_no"].astype(str).str.strip()
    df["comp_id"]   = df["comp_id"].astype(str).str.strip()
    df["weight_kg"] = pd.to_numeric(df["weight_kg"], errors="coerce").fillna(0.0)
    df["length_cm"] = pd.to_numeric(df["length_cm"], errors="coerce")
    return df


def db_save_catches_scored(df: pd.DataFrame) -> None:
    """Replace all scored catches for the active season."""
    season = get_active_season()
    sb = get_supabase()
    sb.table("catches_scored").delete().eq("season_id", season).execute()
    if df.empty:
        return
    tmp = df.copy()
    # Normalise types — Supabase JSON serialiser needs Python-native types
    tmp["weight_kg"] = pd.to_numeric(tmp.get("weight_kg", 0), errors="coerce").fillna(0.0)
    tmp["length_cm"] = pd.to_numeric(tmp.get("length_cm", None), errors="coerce")
    # Convert to string for consistent serialisation (weight_kg will parse on load)
    rows = _rows(tmp, SCORED_COLS, season)
    sb.table("catches_scored").insert(rows).execute()


# ── Team assignments ──────────────────────────────────────────────────────────

def load_team_assignments() -> pd.DataFrame:
    season = get_active_season()
    rows   = _fetch_all("team_assignments", TEAM_COLS, season)
    df = _to_df(rows, TEAM_COLS)
    df["comp_id"]  = df["comp_id"].str.strip()
    df["wp_no"]    = df["wp_no"].str.strip()
    df["sub_team"] = df["sub_team"].str.strip().str.upper()
    return df


def save_team_assignments(df: pd.DataFrame) -> None:
    season = get_active_season()
    sb = get_supabase()
    df = df.copy()
    df["comp_id"]  = df["comp_id"].astype(str).str.strip()
    df["wp_no"]    = df["wp_no"].astype(str).str.strip()
    df["sub_team"] = df["sub_team"].astype(str).str.strip().str.upper()
    df = df[(df["comp_id"] != "") & (df["wp_no"] != "") & (df["sub_team"] != "")]
    df = df[["comp_id", "wp_no", "sub_team"]].drop_duplicates(["comp_id", "wp_no"], keep="last")
    sb.table("team_assignments").delete().eq("season_id", season).execute()
    if not df.empty:
        rows = _rows(df, TEAM_COLS, season)
        sb.table("team_assignments").insert(rows).execute()


# ── Trophy nominees ───────────────────────────────────────────────────────────

def load_trophy_nominees() -> pd.DataFrame:
    season = get_active_season()
    res = (get_supabase()
           .table("trophy_nominees")
           .select(",".join(NOMINEE_COLS))
           .eq("season_id", season)
           .execute())
    return _to_df(res.data, NOMINEE_COLS)


def save_trophy_nominees(df: pd.DataFrame) -> None:
    season = get_active_season()
    sb = get_supabase()
    df = df.copy()
    for c in NOMINEE_COLS:
        if c not in df.columns:
            df[c] = ""
    df = df[NOMINEE_COLS]
    for c in NOMINEE_COLS:
        df[c] = df[c].astype(str).str.strip()
    df = df[(df["trophy"] != "") & (df["wp_no"] != "")]
    df = df.drop_duplicates(NOMINEE_COLS).reset_index(drop=True)
    sb.table("trophy_nominees").delete().eq("season_id", season).execute()
    if not df.empty:
        rows = _rows(df, NOMINEE_COLS, season)
        sb.table("trophy_nominees").insert(rows).execute()


# ── Theme ─────────────────────────────────────────────────────────────────────

def load_theme_db() -> dict:
    """Return the stored theme JSON, or empty dict if not yet configured."""
    try:
        res = get_supabase().table("theme_config").select("theme_json").eq("id", 1).execute()
        if res.data and res.data[0].get("theme_json"):
            return res.data[0]["theme_json"]
    except Exception:
        pass
    return {}


def save_theme_db(theme: dict) -> None:
    """Upsert the theme config singleton row."""
    get_supabase().table("theme_config").upsert(
        {"id": 1, "theme_json": theme},
        on_conflict="id",
    ).execute()
