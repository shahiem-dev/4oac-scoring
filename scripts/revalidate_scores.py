"""Re-score all historical catches with the current rules and report deltas.

Usage:  python scripts/revalidate_scores.py [season]

Reads  data/seasons/<season>/catches_raw.csv
Writes data/seasons/<season>/catches_scored.csv (overwrites)
Prints a diff: catches whose points changed, by how much, with totals per club.

Safe to run repeatedly. Always reads raw + recomputes — no accumulation.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app_lib import (floor2, get_active_season, points_for, season_dir,  # noqa: E402
                     SEASONS_DIR)
from scoring import Scorer  # noqa: E402


def revalidate(season: str) -> None:
    sdir = SEASONS_DIR / season
    raw_p = sdir / "catches_raw.csv"
    scored_p = sdir / "catches_scored.csv"
    anglers_p = sdir / "anglers.csv"
    if not raw_p.exists():
        print(f"[skip] no catches_raw.csv for season {season}")
        return

    raw = pd.read_csv(raw_p, dtype=str).fillna("")
    if raw.empty:
        print(f"[ok] {season}: 0 catches")
        scored_p.write_text("comp_id,wp_no,species_raw,canonical_species,length_cm,weight_kg,edible,status\n",
                            encoding="utf-8")
        return

    # Existing scored (for diff)
    old = pd.read_csv(scored_p, dtype=str).fillna("") if scored_p.exists() else pd.DataFrame()

    scorer = Scorer()
    rows = []
    for _, r in raw.iterrows():
        try:
            L = float(r["length_cm"]) if r["length_cm"] not in ("", None) else None
        except (TypeError, ValueError):
            L = None
        res = scorer.score(r["species_raw"], L)
        pts = points_for(res.weight_kg, res.edible, res.canonical_name)
        rows.append({
            "comp_id": r["comp_id"],
            "wp_no": r["wp_no"],
            "species_raw": r["species_raw"],
            "canonical_species": res.canonical_name or "",
            "length_cm": "" if L is None else L,
            "weight_kg": floor2(res.weight_kg),
            "edible": res.edible,
            "status": res.note,
            "points": pts,
        })

    new = pd.DataFrame(rows)
    # Persist the canonical scored file (without the points column — points are
    # computed on-load by app_lib.load_catches_scored).
    new.drop(columns=["points"]).to_csv(scored_p, index=False)

    # Diff vs old (if old had points; otherwise compute from old fields)
    if not old.empty:
        if "points" not in old.columns:
            old["points"] = old.apply(
                lambda r: points_for(float(r["weight_kg"] or 0), r["edible"],
                                     r.get("canonical_species")), axis=1)
        old["_pts_old"] = old["points"].astype(float)
        new["_pts_new"] = new["points"].astype(float)
        merged = pd.concat([old.reset_index(drop=True), new[["_pts_new"]]], axis=1)
        merged["delta"] = merged["_pts_new"] - merged["_pts_old"]
        changed = merged[merged["delta"].abs() > 0.001]
        print(f"[{season}] {len(raw)} catches scored. {len(changed)} changed.")
        if len(changed):
            cols = ["comp_id", "wp_no", "species_raw", "canonical_species",
                    "weight_kg", "edible", "_pts_old", "_pts_new", "delta"]
            print(changed[cols].to_string(index=False))
    else:
        print(f"[{season}] {len(raw)} catches scored. (no prior scored file to diff)")

    # Per-club totals
    if anglers_p.exists():
        a = pd.read_csv(anglers_p, dtype=str).fillna("")
        m = new.merge(a[["wp_no", "club"]], on="wp_no", how="left")
        m["club"] = m["club"].fillna("UNKNOWN").replace("", "UNKNOWN")
        tot = m.groupby("club")["points"].sum().sort_values(ascending=False)
        print("\nClub totals:")
        for club, pts in tot.items():
            print(f"  {club:15s} {pts:8.2f}")


def main(argv: list[str]) -> int:
    seasons = [argv[1]] if len(argv) > 1 else [get_active_season()]
    for s in seasons:
        revalidate(s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
