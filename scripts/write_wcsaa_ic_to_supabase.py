"""
Stage 4 — write parsed IC 2-8 data to production Supabase (season 2025-26).

Idempotent: re-running wipes the season's anglers/catches/team_assignments and
re-inserts from the parsed CSVs in raw/notes/wcsaa-ic-parsed/.

Preserves WP1268 and WP1354 from current DB (per user decision 2026-06-01).
Skips rescore_all — PDF weights are authoritative.
"""
from __future__ import annotations

import csv
import os
import re
import sys
import tomllib
from pathlib import Path

SCORING_ROOT = Path(r"C:\second-brain\4oac-scoring")
PARSED_DIR   = Path(r"C:\second-brain\raw\notes\wcsaa-ic-parsed")
SEASON_ID    = "2025-26"

KEEP_WPS     = {"WP1268", "WP1354"}  # preserve from current DB even though absent from PDFs


def _load_creds() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if url and key:
        return url, key
    sec = SCORING_ROOT / ".streamlit" / "secrets.toml"
    with open(sec, "rb") as f:
        data = tomllib.load(f)
    return data["SUPABASE_URL"], data["SUPABASE_KEY"]


def _split_name(parsed_name: str) -> tuple[str, str]:
    """'Van Blommenstein, Donald Loydt' -> ('Donald Loydt', 'Van Blommenstein')."""
    if "," not in parsed_name:
        return ("", parsed_name.strip())
    surname, firsts = parsed_name.split(",", 1)
    return (firsts.strip(), surname.strip())


def _norm_team_assn_name(name: str) -> str:
    """Normalize for matching parsed-roster name vs IPC name."""
    return re.sub(r"\s+", " ", name).replace(", ", ",").strip().lower()


def main() -> None:
    from supabase import create_client  # type: ignore
    sb = create_client(*_load_creds())

    # ── Load parsed inputs ─────────────────────────────────────────────────
    roster = list(csv.DictReader((PARSED_DIR / "anglers_roster.csv").open(encoding="utf-8")))
    comps  = list(csv.DictReader((PARSED_DIR / "competitions.csv").open(encoding="utf-8")))
    catches= list(csv.DictReader((PARSED_DIR / "catches.csv").open(encoding="utf-8")))
    teams  = list(csv.DictReader((PARSED_DIR / "team_assignments.csv").open(encoding="utf-8")))

    print(f"Loaded: {len(roster)} anglers, {len(comps)} comps, "
          f"{len(catches)} catches, {len(teams)} team rows")

    # ── Preserve keep-list from current DB ────────────────────────────────
    cur = (sb.table("anglers").select("*")
             .eq("season_id", SEASON_ID).in_("wp_no", list(KEEP_WPS)).execute()).data or []
    cur_by_wp = {r["wp_no"]: r for r in cur}
    print(f"\nPreserving {len(cur_by_wp)} kept anglers: {sorted(cur_by_wp)}")

    # ── Build anglers payload ─────────────────────────────────────────────
    roster_by_wp = {r["wp_no"]: r for r in roster}

    angler_rows: list[dict] = []
    for r in roster:
        first, surname = _split_name(r["name"])
        angler_rows.append({
            "wp_no":           r["wp_no"],
            "sasaa_no":        "",
            "first_name":      first,
            "surname":         surname,
            "club":            r["club"],
            "sub_team":        "",   # per-season default; per-comp overrides go in team_assignments
            "league_division": r["division"],
            "league_code":     r["division"][:1] if r["division"] else "",
            "season_id":       SEASON_ID,
        })
    # Append kept anglers (whose WP isn't in the parsed roster)
    for wp, c in cur_by_wp.items():
        if wp in roster_by_wp:
            continue
        angler_rows.append({
            "wp_no":           wp,
            "sasaa_no":        c.get("sasaa_no", "") or "",
            "first_name":      c.get("first_name", "") or "",
            "surname":         c.get("surname", "") or "",
            "club":            c.get("club", "") or "",
            "sub_team":        c.get("sub_team", "") or "",
            "league_division": c.get("league_division", "") or "",
            "league_code":     c.get("league_code", "") or "",
            "season_id":       SEASON_ID,
        })
    print(f"  Final angler payload: {len(angler_rows)} rows")

    # ── Build competitions payload ────────────────────────────────────────
    comp_rows = [{"comp_id": c["comp_id"], "date": c["date"], "venue": c["venue"],
                  "season_id": SEASON_ID} for c in comps]

    # ── Build catches_raw + catches_scored payload ────────────────────────
    raw_rows:    list[dict] = []
    scored_rows: list[dict] = []
    for c in catches:
        raw_rows.append({
            "comp_id":      c["comp_id"],
            "wp_no":        c["wp_no"],
            "species_raw":  c["species"],
            "length_cm":    c["length_cm"],
            "season_id":    SEASON_ID,
        })
        try:
            w = float(c["weight_kg"])
        except (TypeError, ValueError):
            w = 0.0
        try:
            L_val = float(c["length_cm"])
        except (TypeError, ValueError):
            L_val = None
        scored_rows.append({
            "comp_id":           c["comp_id"],
            "wp_no":             c["wp_no"],
            "species_raw":       c["species"],
            "canonical_species": c["species"],   # trust PDF naming (no alias resolution)
            "length_cm":         L_val,
            "weight_kg":         w,
            "edible":            c["edible"],
            "status":            "ok",
            "season_id":         SEASON_ID,
        })

    # ── Build team_assignments payload (need WP per row) ──────────────────
    # The IPC PDF has Club + Name + sub_team but no WP.
    # We resolve WP by (club, name) against the parsed catches set (which has both).
    name_to_wp: dict[tuple[str, str], str] = {}
    for c in catches:
        key = (c["club"], _norm_team_assn_name(c["name"]))
        name_to_wp.setdefault(key, c["wp_no"])

    team_rows: list[dict] = []
    unresolved: list[dict] = []
    for t in teams:
        key = (t["club"], _norm_team_assn_name(t["name"]))
        wp = name_to_wp.get(key)
        if not wp:
            unresolved.append(t)
            continue
        team_rows.append({
            "comp_id":   t["comp_id"],
            "wp_no":     wp,
            "sub_team":  t["sub_team"],
            "season_id": SEASON_ID,
        })
    # Dedupe (some anglers may appear duplicated in IPC due to extraction noise)
    seen = set()
    deduped = []
    for r in team_rows:
        k = (r["comp_id"], r["wp_no"])
        if k in seen: continue
        seen.add(k); deduped.append(r)
    team_rows = deduped
    print(f"  Resolved {len(team_rows)} team-assignment rows (unresolved: {len(unresolved)})")
    if unresolved[:3]:
        print("  Sample unresolved:")
        for u in unresolved[:3]:
            print(f"    {u}")

    # ── Write — bulk inserts in chunks of 500 to stay under PostgREST limits
    def _bulk(table: str, rows: list[dict], chunk: int = 500) -> None:
        for i in range(0, len(rows), chunk):
            sb.table(table).insert(rows[i:i+chunk]).execute()

    print("\n=== EXECUTING WRITES ===")

    # 1. Anglers — delete then insert
    n_del = len(sb.table("anglers").delete().eq("season_id", SEASON_ID).execute().data or [])
    print(f"  anglers          deleted={n_del}")
    _bulk("anglers", angler_rows)
    print(f"  anglers          inserted={len(angler_rows)}")

    # 2. Competitions — upsert (some may pre-exist with different venues)
    sb.table("competitions").delete().eq("season_id", SEASON_ID).execute()
    _bulk("competitions", comp_rows)
    print(f"  competitions     reset={len(comp_rows)}")

    # 3. catches_raw + catches_scored
    sb.table("catches_raw").delete().eq("season_id", SEASON_ID).execute()
    sb.table("catches_scored").delete().eq("season_id", SEASON_ID).execute()
    _bulk("catches_raw", raw_rows)
    print(f"  catches_raw      inserted={len(raw_rows)}")
    _bulk("catches_scored", scored_rows)
    print(f"  catches_scored   inserted={len(scored_rows)}")

    # 4. team_assignments
    sb.table("team_assignments").delete().eq("season_id", SEASON_ID).execute()
    _bulk("team_assignments", team_rows)
    print(f"  team_assignments inserted={len(team_rows)}")

    print("\n✓ Write complete. Skipping rescore_all — PDF weights are authoritative.")


if __name__ == "__main__":
    main()
