"""
One-time migration script — load all existing CSV data into Supabase.

Run ONCE after creating the Supabase tables (supabase_schema.sql).
Safe to re-run: uses upsert/delete-then-insert so it won't create duplicates.

Usage (local):
    set SUPABASE_URL=https://xjblbdjavjmzrfzdgrdk.supabase.co
    set SUPABASE_KEY=<your_service_role_key>
    python migrate_csv_to_supabase.py

Or create a .env file:
    SUPABASE_URL=...
    SUPABASE_KEY=...
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd

# ── Bootstrap: read credentials from env or secrets.toml ─────────────────────

def _get_creds() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if url and key:
        return url, key
    # Try .streamlit/secrets.toml
    secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        try:
            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib  # type: ignore
                except ImportError:
                    tomllib = None
            if tomllib:
                with open(secrets_path, "rb") as f:
                    sec = tomllib.load(f)
                url = sec.get("SUPABASE_URL", "")
                key = sec.get("SUPABASE_KEY", "")
                if url and key:
                    return url, key
        except Exception as e:
            print(f"  Warning: could not parse secrets.toml: {e}")
    if not url or not key:
        print("ERROR: Set SUPABASE_URL and SUPABASE_KEY environment variables.")
        print("       Or add them to .streamlit/secrets.toml.")
        sys.exit(1)
    return url, key


def _get_client():
    url, key = _get_creds()
    from supabase import create_client
    return create_client(url, key)


# ── Migration logic ───────────────────────────────────────────────────────────

DATA_DIR    = Path(__file__).parent / "data"
SEASONS_DIR = DATA_DIR / "seasons"


def migrate_seasons(sb) -> list[str]:
    """Create season rows; mark the one in active_season.txt as active."""
    active_file = DATA_DIR / "active_season.txt"
    active = active_file.read_text(encoding="utf-8").strip() if active_file.exists() else ""
    seasons = [d.name for d in SEASONS_DIR.iterdir() if d.is_dir()] if SEASONS_DIR.exists() else []
    if not seasons:
        print("  No seasons found in data/seasons/ — nothing to migrate.")
        return []
    for s in seasons:
        sb.table("seasons").upsert(
            {"season_id": s, "is_active": (s == active)},
            on_conflict="season_id",
        ).execute()
        flag = " ← active" if s == active else ""
        print(f"  Created season: {s}{flag}")
    return seasons


def migrate_anglers(sb, season: str) -> int:
    f = SEASONS_DIR / season / "anglers.csv"
    if not f.exists():
        return 0
    df = pd.read_csv(f, dtype=str).fillna("")
    if df.empty:
        return 0
    rows = df.to_dict(orient="records")
    for r in rows:
        r["season_id"] = season
    sb.table("anglers").delete().eq("season_id", season).execute()
    sb.table("anglers").insert(rows).execute()
    return len(rows)


def migrate_competitions(sb, season: str) -> int:
    f = SEASONS_DIR / season / "competitions.csv"
    if not f.exists():
        return 0
    df = pd.read_csv(f, dtype=str).fillna("")
    if df.empty:
        return 0
    rows = df.to_dict(orient="records")
    for r in rows:
        r["season_id"] = season
    sb.table("competitions").delete().eq("season_id", season).execute()
    sb.table("competitions").insert(rows).execute()
    return len(rows)


def migrate_catches_raw(sb, season: str) -> int:
    f = SEASONS_DIR / season / "catches_raw.csv"
    if not f.exists():
        return 0
    df = pd.read_csv(f, dtype=str).fillna("")
    if df.empty:
        return 0
    rows = df.to_dict(orient="records")
    for r in rows:
        r["season_id"] = season
    sb.table("catches_raw").delete().eq("season_id", season).execute()
    sb.table("catches_raw").insert(rows).execute()
    return len(rows)


def migrate_catches_scored(sb, season: str) -> int:
    f = SEASONS_DIR / season / "catches_scored.csv"
    if not f.exists():
        return 0
    df = pd.read_csv(f, dtype=str).fillna("")
    if df.empty:
        return 0
    rows = df.to_dict(orient="records")
    for r in rows:
        r["season_id"] = season
    sb.table("catches_scored").delete().eq("season_id", season).execute()
    sb.table("catches_scored").insert(rows).execute()
    return len(rows)


def migrate_team_assignments(sb, season: str) -> int:
    f = SEASONS_DIR / season / "team_assignments.csv"
    if not f.exists():
        return 0
    df = pd.read_csv(f, dtype=str).fillna("")
    if df.empty:
        return 0
    rows = df.to_dict(orient="records")
    for r in rows:
        r["season_id"] = season
    sb.table("team_assignments").delete().eq("season_id", season).execute()
    sb.table("team_assignments").insert(rows).execute()
    return len(rows)


def migrate_trophy_nominees(sb, season: str) -> int:
    f = SEASONS_DIR / season / "trophy_nominees.csv"
    if not f.exists():
        return 0
    df = pd.read_csv(f, dtype=str).fillna("")
    if df.empty:
        return 0
    rows = df.to_dict(orient="records")
    for r in rows:
        r["season_id"] = season
    sb.table("trophy_nominees").delete().eq("season_id", season).execute()
    sb.table("trophy_nominees").insert(rows).execute()
    return len(rows)


def migrate_theme(sb) -> bool:
    f = DATA_DIR / "theme.json"
    if not f.exists():
        return False
    try:
        theme = json.loads(f.read_text(encoding="utf-8"))
        sb.table("theme_config").upsert(
            {"id": 1, "theme_json": theme}, on_conflict="id"
        ).execute()
        return True
    except Exception as e:
        print(f"  Warning: theme migration failed: {e}")
        return False


def run() -> None:
    print("WCSAA Scoring — CSV → Supabase migration")
    print("=" * 50)

    sb = _get_client()
    print("Connected to Supabase.\n")

    # Seasons
    print("Migrating seasons...")
    seasons = migrate_seasons(sb)
    print(f"  Done: {len(seasons)} season(s).\n")

    # Per-season data
    for season in seasons:
        print(f"Season: {season}")
        n = migrate_anglers(sb, season)
        print(f"  Anglers:         {n}")
        n = migrate_competitions(sb, season)
        print(f"  Competitions:    {n}")
        n = migrate_catches_raw(sb, season)
        print(f"  Catches (raw):   {n}")
        n = migrate_catches_scored(sb, season)
        print(f"  Catches (scored):{n}")
        n = migrate_team_assignments(sb, season)
        print(f"  Team assignments:{n}")
        n = migrate_trophy_nominees(sb, season)
        print(f"  Trophy nominees: {n}")
        print()

    # Theme
    print("Migrating theme config...")
    ok = migrate_theme(sb)
    print(f"  {'Done.' if ok else 'No theme.json found — using defaults.'}\n")

    print("Migration complete.")
    print("You can now remove SUPABASE_URL and SUPABASE_KEY from your env")
    print("and add them to .streamlit/secrets.toml (local) or Streamlit Cloud secrets.")


if __name__ == "__main__":
    run()
