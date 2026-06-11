"""
Claude-powered WCSAA IC PDF extractor — replacement for the regex parser
(parse_wcsaa_ic_pdfs.py). Sends each PDF to Claude with a strict JSON schema
(structured outputs) so the model does the layout understanding instead of
brittle line regexes.

Reads:
  C:/second-brain/raw/pdfs/wcsaa-2025-26/IC {n}/
    Details of Fish Caught*.pdf
    Individual Position in Club*.pdf
    Overall Individual Position per Division*.pdf  (or per League)

Writes (default raw/notes/wcsaa-ic-parsed-claude/ — same four CSVs as the
regex parser so the downstream Stage-4 writer works unchanged):
  competitions.csv         comp_id, date, venue
  catches.csv              comp_id, wp_no, name, club, species, weight_kg, length_cm, edible
  team_assignments.csv     comp_id, club, name, sub_team
  anglers_roster.csv       wp_no, name, club, division

Usage:
  python scripts/parse_wcsaa_ic_pdfs_claude.py            # all ICs 1-8
  python scripts/parse_wcsaa_ic_pdfs_claude.py --ic 5     # one IC
  python scripts/parse_wcsaa_ic_pdfs_claude.py --compare  # diff vs regex output

API key: ANTHROPIC_API_KEY env var, or ANTHROPIC_API_KEY in
4oac-scoring/.streamlit/secrets.toml (never committed).

No database writes. No mutations to raw/. Idempotent.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import sys
from pathlib import Path

import anthropic

RAW_ROOT    = Path(r"C:\second-brain\raw\pdfs\wcsaa-2025-26")
OUT_DIR     = Path(r"C:\second-brain\raw\notes\wcsaa-ic-parsed-claude")
REGEX_DIR   = Path(r"C:\second-brain\raw\notes\wcsaa-ic-parsed")
SECRETS     = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"

MODEL = "claude-opus-4-8"
IC_RANGE = range(1, 9)


# ── API key resolution ───────────────────────────────────────────────────────

def get_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key and SECRETS.exists():
        import tomllib
        with SECRETS.open("rb") as f:
            key = tomllib.load(f).get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit(
            "ERROR: no API key. Set ANTHROPIC_API_KEY env var or add it to "
            f"{SECRETS}"
        )
    return anthropic.Anthropic(api_key=key)


# ── JSON schemas (structured outputs) ────────────────────────────────────────
# additionalProperties: false on every object is required by the API.

DETAILS_SCHEMA = {
    "type": "object",
    "properties": {
        "date":  {"type": "string", "description": "Competition date as YYYY-MM-DD"},
        "venue": {"type": "string", "description": "Venue name from the header, e.g. 'West Coast'"},
        "catches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "wp_no":     {"type": "string", "description": "Angler WP number, zero-padded to 4 digits, e.g. WP0320"},
                    "name":      {"type": "string", "description": "Angler name exactly as printed: 'Surname,Firstname(s)' incl. suffixes like (Jnr)"},
                    "club":      {"type": "string", "description": "Club the angler is listed under (from the TEAM <CLUB> section header)"},
                    "species":   {"type": "string", "description": "Full species text incl. parenthesised qualifiers, e.g. 'Shark (Cow) (Sevengill)'. For manual point allocations use the printed text, e.g. 'Average Score'"},
                    "weight_kg": {"type": "number", "description": "Weight in kg. Rows marked '< 1 kg' are 0.0"},
                    "length_cm": {"type": "number"},
                    "edible":    {"type": "string", "enum": ["Y", "N"]},
                },
                "required": ["wp_no", "name", "club", "species", "weight_kg", "length_cm", "edible"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["date", "venue", "catches"],
    "additionalProperties": False,
}

IPC_SCHEMA = {
    "type": "object",
    "properties": {
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "club":     {"type": "string"},
                    "name":     {"type": "string", "description": "'Surname,Firstname(s)' exactly as printed"},
                    "sub_team": {"type": "string", "description": "Sub-team letter A-I"},
                },
                "required": ["club", "name", "sub_team"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["rows"],
    "additionalProperties": False,
}

DIV_SCHEMA = {
    "type": "object",
    "properties": {
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "wp_no":    {"type": "string", "description": "WP number zero-padded to 4 digits"},
                    "name":     {"type": "string"},
                    "club":     {"type": "string"},
                    "division": {"type": "string", "description": "Division/league letter from the last column"},
                },
                "required": ["wp_no", "name", "club", "division"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["rows"],
    "additionalProperties": False,
}

KNOWN_CLUBS = ["BLUE RAY", "FALSEBAY", "FOUR OCEANS", "GOODWOOD",
               "POLICE", "TWO OCEANS", "TYGERBERG"]

DETAILS_PROMPT = f"""Extract every catch row from this WCSAA 'Details of Fish Caught' PDF.

Rules:
- The header line gives the date and venue: 'DETAIL OF FISH CAUGHT: YYYY/MM/DD Comp N - Venue'. Return the date as YYYY-MM-DD.
- Catches are grouped under 'TEAM <CLUB>' section headers. Valid clubs: {", ".join(KNOWN_CLUBS)}. Assign each catch the club of the section it appears under.
- Each catch row: WP number, angler name ('Surname,Firstname(s)', may include multi-word surnames like 'Janse Van Rensburg', multi-word first names, initials, or suffixes like '(Jnr)'), species text, weight (comma decimal, e.g. '49,38' = 49.38), length, edible Y/N.
- Species text may contain parentheses, e.g. 'Guitarfish (Bluntnose)(M)' or 'Site Fish (Catfish - White Sea)'. Keep it verbatim. Do NOT let any part of the angler's name leak into the species field.
- Rows marked '< 1 kg' have weight_kg 0.0 (sub-minimum fish). Keep the row.
- Some rows are manual point allocations, not fish (e.g. 'Average Score' for anglers on national duty). Include them verbatim as the species.
- Zero-pad WP numbers to 4 digits: WP320 -> WP0320.
- Include EVERY row on EVERY page. Do not deduplicate, do not skip zero-weight rows."""

IPC_PROMPT = """Extract every row from this WCSAA 'Individual Position in Club' PDF.

Each row has: club name, angler name ('Surname,Firstname(s)'), total points, and a sub-team letter (A-I) in the last column. Return club, name and sub_team for every row on every page. Skip headers and club subtotal/total lines that have no angler name."""

DIV_PROMPT = """Extract every angler row from this WCSAA 'Overall Individual Position per Division/League' PDF.

Each row has: position, WP number, angler name ('Surname,Firstname(s)'), club, several per-competition point columns, a total, and a division/league letter in the last column. Return wp_no (zero-padded to 4 digits, e.g. WP320 -> WP0320), name, club and division for every row on every page. Skip header and subtotal lines."""


# ── Extraction ───────────────────────────────────────────────────────────────

def extract(client: anthropic.Anthropic, pdf_path: Path, prompt: str, schema: dict) -> dict:
    """Send one PDF to Claude with a strict output schema; return parsed JSON."""
    pdf_b64 = base64.standard_b64encode(pdf_path.read_bytes()).decode()
    with client.messages.stream(
        model=MODEL,
        max_tokens=64000,
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_b64,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "max_tokens":
        raise RuntimeError(f"{pdf_path.name}: output truncated at max_tokens")
    text = next(b.text for b in msg.content if b.type == "text")
    return json.loads(text)


def _norm_wp(wp: str) -> str:
    m = re.match(r"WP(\d+)$", wp.strip())
    return "WP" + m.group(1).zfill(4) if m else wp.strip()


def _find_one(folder: Path, glob_pat: str) -> Path | None:
    matches = sorted(folder.glob(glob_pat))
    return matches[0] if matches else None


def run(ics: list[int]) -> None:
    client = get_client()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    competitions: list[dict] = []
    all_catches:  list[dict] = []
    all_teams:    list[dict] = []
    all_div:      list[dict] = []

    for n in ics:
        folder = RAW_ROOT / f"IC {n}"
        if not folder.exists():
            print(f"  WARN: {folder} missing - skipping")
            continue

        details = _find_one(folder, "Details of Fish Caught*.pdf")
        ipc     = _find_one(folder, "Individual Position in Club*.pdf")
        div     = (_find_one(folder, "Overall Individual Position per Division*.pdf")
                   or _find_one(folder, "Overall Individual Position per League*.pdf"))

        if not details:
            print(f"  ERROR: IC {n} missing Details PDF - skipping")
            continue

        print(f"  IC {n}: extracting Details ({details.name}) ...", flush=True)
        d = extract(client, details, DETAILS_PROMPT, DETAILS_SCHEMA)
        competitions.append({"comp_id": n, "date": d["date"], "venue": d["venue"]})
        for c in d["catches"]:
            c["comp_id"] = n
            c["wp_no"] = _norm_wp(c["wp_no"])
        all_catches.extend(d["catches"])
        print(f"        {d['date']} {d['venue']:<14} catches={len(d['catches'])}")

        if ipc:
            print(f"  IC {n}: extracting IPC ...", flush=True)
            r = extract(client, ipc, IPC_PROMPT, IPC_SCHEMA)
            for row in r["rows"]:
                row["comp_id"] = n
            all_teams.extend(r["rows"])
            print(f"        team_rows={len(r['rows'])}")

        if div:
            print(f"  IC {n}: extracting Division ...", flush=True)
            r = extract(client, div, DIV_PROMPT, DIV_SCHEMA)
            for row in r["rows"]:
                row["comp_id"] = n
                row["wp_no"] = _norm_wp(row["wp_no"])
            all_div.extend(r["rows"])
            print(f"        div_rows={len(r['rows'])}")

    def write(name: str, rows: list[dict], fields: list[str]) -> None:
        path = OUT_DIR / name
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"  wrote {path}  ({len(rows)} rows)")

    print("\n-- Output --")
    write("competitions.csv", competitions, ["comp_id", "date", "venue"])
    write("catches.csv", all_catches,
          ["comp_id", "wp_no", "name", "club", "species", "weight_kg", "length_cm", "edible"])
    write("team_assignments.csv", all_teams,
          ["comp_id", "club", "name", "sub_team"])

    roster: dict[str, dict] = {}
    for r in sorted(all_div, key=lambda x: x.get("comp_id", 0)):
        roster[r["wp_no"]] = {k: r[k] for k in ("wp_no", "name", "club", "division")}
    for c in all_catches:
        roster.setdefault(c["wp_no"], {
            "wp_no": c["wp_no"], "name": c["name"], "club": c["club"], "division": "",
        })
    write("anglers_roster.csv", list(roster.values()),
          ["wp_no", "name", "club", "division"])


# ── Compare against the regex parser's output ────────────────────────────────

def compare() -> None:
    """Row-level diff of catches.csv between the Claude and regex outputs."""
    def load(path: Path) -> list[tuple]:
        with path.open(encoding="utf-8") as f:
            return [
                (r["comp_id"], r["wp_no"], r["species"],
                 f"{float(r['weight_kg']):.2f}", r["edible"])
                for r in csv.DictReader(f)
            ]

    a_path = OUT_DIR / "catches.csv"
    b_path = REGEX_DIR / "catches.csv"
    for p in (a_path, b_path):
        if not p.exists():
            sys.exit(f"ERROR: {p} not found - run both parsers first")

    from collections import Counter
    a, b = Counter(load(a_path)), Counter(load(b_path))
    only_claude = a - b
    only_regex  = b - a
    print(f"claude rows: {sum(a.values())}   regex rows: {sum(b.values())}")
    print(f"rows only in claude output: {sum(only_claude.values())}")
    for row, cnt in sorted(only_claude.items())[:30]:
        print(f"  +{cnt} {row}")
    print(f"rows only in regex output: {sum(only_regex.values())}")
    for row, cnt in sorted(only_regex.items())[:30]:
        print(f"  -{cnt} {row}")
    if not only_claude and not only_regex:
        print("IDENTICAL - safe to swap parsers.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ic", type=int, choices=list(IC_RANGE),
                    help="extract a single IC (default: all)")
    ap.add_argument("--compare", action="store_true",
                    help="diff catches.csv against the regex parser's output")
    args = ap.parse_args()
    if args.compare:
        compare()
    else:
        run([args.ic] if args.ic else list(IC_RANGE))
