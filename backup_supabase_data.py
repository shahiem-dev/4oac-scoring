"""
Backup script — export all Supabase data to local CSV files.

Run this:
  - Before any significant code change
  - After every git push to main
  - On a schedule (set up a GitHub Actions cron or run manually)

Usage:
    python backup_supabase_data.py

Credentials are read from .streamlit/secrets.toml (local) or
SUPABASE_URL / SUPABASE_KEY environment variables.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


def _get_creds() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if url and key:
        return url, key
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
        print("ERROR: Set SUPABASE_URL and SUPABASE_KEY (env or .streamlit/secrets.toml).")
        sys.exit(1)
    return url, key


def _get_client():
    url, key = _get_creds()
    from supabase import create_client
    return create_client(url, key)


BACKUP_DIR = Path(__file__).parent / "backups"


def _dump_table(sb, table: str, out_dir: Path) -> int:
    """Fetch all rows from a table and write to CSV."""
    res = sb.table(table).select("*").execute()
    rows = res.data or []
    if not rows:
        pd.DataFrame().to_csv(out_dir / f"{table}.csv", index=False)
        return 0
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / f"{table}.csv", index=False)
    return len(rows)


def run() -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = BACKUP_DIR / f"{ts}_supabase"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"WCSAA Scoring — Supabase backup → {out_dir}")
    print("=" * 60)

    sb = _get_client()
    print("Connected.\n")

    tables = [
        "seasons",
        "anglers",
        "competitions",
        "catches_raw",
        "catches_scored",
        "team_assignments",
        "trophy_nominees",
        "theme_config",
    ]

    total = 0
    for t in tables:
        n = _dump_table(sb, t, out_dir)
        print(f"  {t:<22} {n:>5} rows")
        total += n

    # Write manifest
    manifest = {
        "timestamp":  ts,
        "source":     "supabase",
        "tables":     tables,
        "total_rows": total,
    }
    (out_dir / "BACKUP_MANIFEST.txt").write_text(
        "\n".join(f"{k}: {v}" for k, v in manifest.items()),
        encoding="utf-8",
    )

    print(f"\nBackup complete — {total} rows saved to {out_dir}")


if __name__ == "__main__":
    run()
