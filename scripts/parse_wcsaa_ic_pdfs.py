"""
Parse WCSAA 2025-26 IC 2..8 PDFs into intermediate CSVs.

Reads:
  C:/second-brain/raw/pdfs/wcsaa-2025-26/IC {n}/
    Details of Fish Caught*.pdf
    Individual Position in Club*.pdf
    Overall Individual Position per Division*.pdf  (or per League)

Writes (to raw/notes/wcsaa-ic-parsed/):
  competitions.csv         comp_id, date, venue
  catches.csv              comp_id, wp_no, name, club, species, weight_kg, length_cm, edible
  team_assignments.csv     comp_id, wp_no, club, sub_team
  anglers_roster.csv       wp_no, name, club, division  (canonical from per-division PDFs)

No database writes. No mutations to raw/. Idempotent — re-running overwrites CSVs.
"""
from __future__ import annotations

import csv
import glob
import os
import re
import sys
from pathlib import Path

try:
    import pypdf
except ImportError:
    print("ERROR: pypdf not installed. Run: pip install --user pypdf")
    sys.exit(1)

RAW_ROOT = Path(r"C:\second-brain\raw\pdfs\wcsaa-2025-26")
OUT_DIR  = Path(r"C:\second-brain\raw\notes\wcsaa-ic-parsed")

IC_RANGE = range(2, 9)

# ── Regex patterns ────────────────────────────────────────────────────────────

# Details header e.g.: "DETAIL OF FISH CAUGHT: 2025/10/18 Comp 2 - West Coast"
HDR_DETAIL = re.compile(
    r"DETAIL OF FISH CAUGHT:\s*(\d{4}/\d{2}/\d{2})\s+Comp\s+(\d+)\s*-\s*(.+?)\s*$",
    re.MULTILINE,
)

# Catch row. Format varies but right-anchored as: <weight> <length> <edible>
# Weight may be prefixed with "< 1 kg" (sub-minimum marker glued to 0,00).
# Examples that must parse:
#   WP0320 Abrahams,Saddeeq Site Fish (Catfish - White Sea) 1,00 66,00 N
#   WP0320 Abrahams,Saddeeq Guitarfish (Bluntnose)(M) < 1 kg0,00 63,00 N
#   WP0033 Naicker,Anand Shark (Cow) (Sevengill) 49,38 154,00 N
CATCH = re.compile(
    r"^(WP\d{3,5})\s+"            # 1 WP id
    r"(.+?)\s+"                    # 2 name + species (split later)
    r"(?:<\s*\d+\s*kg)?"           # optional "< 1 kg" prefix on weight
    r"(\d{1,3},\d{2})\s+"          # 3 weight  (comma decimal)
    r"(\d{1,3}(?:[,.]\d{2})?)\s+"  # 4 length
    r"([YN])\s*$"                  # 5 edible flag
)

# Name pattern: "LastName,FirstName" or "LastName, FirstName" possibly with
# spaces/initials/apostrophes in either part. Examples:
#   "Abrahams,Saddeeq" / "De Jongh,Wilhelm" / "Pretorius, Rickus"
#   "Janse Van Rensburg,Sakkie" / "Groenewald, Adriaan S"
NAME = re.compile(
    r"([A-Za-z][A-Za-z'’\.\-\(\) ]+?,\s*[A-Z][A-Za-z'’\.\-\(\) ]*?)\s+"
)

CLUB_HEADER = re.compile(r"^TEAM\s+([A-Z][A-Z &]+?)\s*$")

# Known WCSAA clubs (extracted from Details PDFs). Order matters: longer first
# so "FOUR OCEANS" matches before any prefix subset.
KNOWN_CLUBS = [
    "BLUE RAY", "FALSEBAY", "FOUR OCEANS", "GOODWOOD",
    "POLICE", "TWO OCEANS", "TYGERBERG",
]
CLUB_ALT = "|".join(re.escape(c) for c in sorted(KNOWN_CLUBS, key=len, reverse=True))

# Individual Position in Club row:
#   "BLUE RAY Naicker,Anand 55,01 A"
IPC_ROW = re.compile(
    rf"^({CLUB_ALT})\s+"                 # 1 CLUB (anchored to known list)
    r"([A-Z][A-Za-z'’\.\-\(\) ]+?,\s*[A-Z][A-Za-z'’\.\-\(\) ]*?)\s+"  # 2 NAME
    r"(-?\d{1,4},\d{2})\s+"              # 3 total points
    r"([A-I])\s*$"                       # 4 sub-team letter
)

# Per-Division row (Overall Individual Position per Division/League):
#   "1,00 WP1326 Sims, Tommy FALSEBAY 0,00 76,84 ... 76,84 G"
DIV_ROW = re.compile(
    rf"^\s*\d+,\d{{2}}\s+"               # position
    r"(WP\d{3,5})\s+"                    # 1 WP id
    r"([A-Z][A-Za-z'’\.\-\(\) ]+?,\s*[A-Z][A-Za-z'’\.\-\(\) ]*?)\s+"  # 2 NAME
    rf"({CLUB_ALT})\s+"                  # 3 CLUB (anchored to known list)
    r"(?:-?\d{1,4},\d{2}\s+){2,}"        # per-comp points + total
    r"([A-Z])\s*$"                       # 4 division letter
)


def _norm_wp(wp: str) -> str:
    """WP123 → WP0123 (4-digit zero-pad)."""
    m = re.match(r"WP(\d+)$", wp)
    if not m:
        return wp
    return "WP" + m.group(1).zfill(4)


def _num(s: str) -> float:
    """European decimal '1,23' → 1.23."""
    return float(s.replace(",", "."))


SPECIES_PREFIXES = {
    "Shark","Guitarfish","Stingray","Ray","Skate","Site","Catshark","Kob",
    "Steenbras","Cape","Yellowtail","Snoek","Hottentot","Galjoen","Belman",
    "Mackerel","Geelbek","Garrick","Elephant","Eel","Stumpnose","Strepie",
    "Blacktail","White","Springer","Soupfin","Spotted","Cob","Hound",
    "Baardman","Bronze","Copper","Smooth","Gurnard","Catfish","Octopus",
    "Elf","Shad","Musselcracker","Bream","Mullet","Roman","Steentjie",
    "Maasbanker","Anchovy","Sardine","Pinky","Pignose","Sand","Sole",
    "Klipfish","Klipvis","Klipper","Klippie","Karanteen","Knorhaan",
    "Black","Red","Silver","Blue","Yellow","Green","Common","Lesser",
    "Greater","Banded","Striped","Two","Devil","Star","Coral","Reef",
    "Stone","Mud","Sea","Pajama","Saw","Spearnose","Speckled","Hagfish",
    "Bluntnose","Halfbeak","Garfish","Needlefish","Marlin","Tuna","Bonito",
    "Yellowfin","Skipjack","Albacore","Mossbanker","Hake","Rockcod","Zebra",
    # Manual point allocations (e.g. national duty replacement scores)
    "Average",
}


def _split_name_species(blob: str) -> tuple[str, str]:
    """Split 'Lastname,Firstnames Species Words' into (name, species).

    Strategy: walk left-to-right and find the first word that is a known
    species prefix. Everything before = name, from there to end = species.
    This is robust against multi-word first names like 'Marc Lindsay' and
    parenthesised suffixes like '(Jnr)'.
    """
    words = blob.split()
    for i, w in enumerate(words):
        if w in SPECIES_PREFIXES:
            return " ".join(words[:i]).strip(), " ".join(words[i:]).strip()
    # Fallback: try NAME regex
    m = NAME.match(blob + " ")
    if m:
        name = m.group(1).strip()
        species = blob[len(name):].strip().lstrip(",").strip()
        return name, species
    return blob, ""


def parse_details(pdf_path: Path, comp_id: int) -> tuple[str, str, list[dict]]:
    """Return (date, venue, [catch rows])."""
    rdr = pypdf.PdfReader(str(pdf_path))
    rows: list[dict] = []
    date = ""
    venue = ""
    current_club = ""

    for page in rdr.pages:
        txt = page.extract_text() or ""
        for line in txt.splitlines():
            line = line.strip()
            if not line:
                continue
            # Header (only first page usually)
            hm = HDR_DETAIL.search(line)
            if hm:
                date  = hm.group(1).replace("/", "-")
                venue = hm.group(3).strip()
                continue
            # Club header
            ch = CLUB_HEADER.match(line)
            if ch:
                current_club = ch.group(1).strip()
                continue
            # Skip column headers
            if line.startswith("NO ANGLER") or line.startswith("Pos") or "ANGLER SPECIE" in line:
                continue
            # Catch row
            cm = CATCH.match(line)
            if not cm:
                continue
            wp = _norm_wp(cm.group(1))
            blob = cm.group(2).strip()
            weight = _num(cm.group(3))
            length = _num(cm.group(4))
            edible = cm.group(5)
            name, species = _split_name_species(blob)
            # If weight came from "< 1 kg" marker, force 0
            if "< 1 kg" in line or "<1 kg" in line:
                weight = 0.0
            rows.append({
                "comp_id":   comp_id,
                "wp_no":     wp,
                "name":      name,
                "club":      current_club,
                "species":   species,
                "weight_kg": weight,
                "length_cm": length,
                "edible":    edible,
            })
    return date, venue, rows


def parse_ipc(pdf_path: Path, comp_id: int) -> list[dict]:
    """Return list of {comp_id, club, name, sub_team}."""
    rdr = pypdf.PdfReader(str(pdf_path))
    out: list[dict] = []
    for page in rdr.pages:
        for line in (page.extract_text() or "").splitlines():
            line = line.strip()
            m = IPC_ROW.match(line)
            if not m:
                continue
            out.append({
                "comp_id":  comp_id,
                "club":     m.group(1).strip(),
                "name":     m.group(2).strip(),
                "sub_team": m.group(4),
            })
    return out


def parse_division(pdf_path: Path) -> list[dict]:
    """Return [{wp_no, name, club, division}] from a per-division PDF.

    Division letter mapping: G=Grandmaster, M=Master, S=Senior, J=Junior, L=Lady,
    (we leave the raw letter; downstream code can map to full names).
    """
    rdr = pypdf.PdfReader(str(pdf_path))
    out: list[dict] = []
    for page in rdr.pages:
        for line in (page.extract_text() or "").splitlines():
            line = line.strip()
            m = DIV_ROW.match(line)
            if not m:
                continue
            out.append({
                "wp_no":    _norm_wp(m.group(1)),
                "name":     m.group(2).strip(),
                "club":     m.group(3).strip(),
                "division": m.group(4),
            })
    return out


def _find_one(folder: Path, glob_pat: str) -> Path | None:
    matches = sorted(folder.glob(glob_pat))
    return matches[0] if matches else None


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    competitions: list[dict] = []
    all_catches:  list[dict] = []
    all_teams:    list[dict] = []
    all_div:      list[dict] = []

    for n in IC_RANGE:
        folder = RAW_ROOT / f"IC {n}"
        if not folder.exists():
            print(f"  WARN: {folder} missing — skipping")
            continue

        details = _find_one(folder, "Details of Fish Caught*.pdf")
        ipc     = _find_one(folder, "Individual Position in Club*.pdf")
        div     = _find_one(folder, "Overall Individual Position per Division*.pdf") \
                  or _find_one(folder, "Overall Individual Position per League*.pdf")

        if not details:
            print(f"  ERROR: IC {n} missing Details PDF — skipping")
            continue

        date, venue, catches = parse_details(details, comp_id=n)
        competitions.append({"comp_id": n, "date": date, "venue": venue})
        all_catches.extend(catches)
        print(f"  IC {n}: {date} {venue:<14} catches={len(catches):>4}", end="")

        if ipc:
            teams = parse_ipc(ipc, comp_id=n)
            all_teams.extend(teams)
            print(f"  team_rows={len(teams):>3}", end="")
        else:
            print("  team_rows=MISSING", end="")

        if div:
            divs = parse_division(div)
            for d in divs:
                d["comp_id"] = n
            all_div.extend(divs)
            print(f"  div_rows={len(divs):>3}")
        else:
            print("  div_rows=MISSING")

    # Write CSVs
    def write(name: str, rows: list[dict], fields: list[str]) -> None:
        path = OUT_DIR / name
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print(f"  wrote {path}  ({len(rows)} rows)")

    print("\n-- Output --")
    write("competitions.csv", competitions, ["comp_id", "date", "venue"])
    write("catches.csv", all_catches,
          ["comp_id", "wp_no", "name", "club", "species", "weight_kg", "length_cm", "edible"])
    write("team_assignments.csv", all_teams,
          ["comp_id", "club", "name", "sub_team"])
    # Roster: dedupe by wp_no.
    # Primary source: per-division PDFs (has WP + canonical name + club + division).
    # Augment: any WP that appears in catches but not in division PDFs gets added
    # with division blank and club/name from the first catch row.
    roster: dict[str, dict] = {}
    for r in sorted(all_div, key=lambda x: x.get("comp_id", 0)):
        roster[r["wp_no"]] = {
            "wp_no":    r["wp_no"],
            "name":     r["name"],
            "club":     r["club"],
            "division": r["division"],
        }
    # Catch-only anglers (no division-PDF entry across IC 2–8)
    for c in all_catches:
        wp = c["wp_no"]
        if wp in roster:
            continue
        roster[wp] = {
            "wp_no":    wp,
            "name":     c["name"],
            "club":     c["club"],
            "division": "",
        }
    write("anglers_roster.csv", list(roster.values()),
          ["wp_no", "name", "club", "division"])


if __name__ == "__main__":
    main()
