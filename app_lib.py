"""Shared helpers for the Streamlit app — season-aware CSV data layer + scoring.

Data layout:
    data/
        active_season.txt           # plain text, e.g. "2025-26"
        species_master.csv          # shared across seasons
        species_aliases.json        # shared across seasons
        seasons/
            2025-26/
                anglers.csv
                competitions.csv
                catches_raw.csv
                catches_scored.csv
            2026-27/
                ...
"""
from __future__ import annotations

import math
import re
import shutil
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SCRIPTS = ROOT / "scripts"
SEASONS_DIR = DATA / "seasons"
ACTIVE_FILE = DATA / "active_season.txt"
LOGOS_DIR = DATA / "logos"
LOGO_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")

sys.path.insert(0, str(SCRIPTS))
from scoring import Scorer  # noqa: E402

# Scoring rule (mirrors scripts/generate_reports.py)
EDIBLE_PTS_PER_KG = 4.0
NON_EDIBLE_PTS_PER_KG = 1.0
EDIBLE_MIN_KG = 0.5      # edible catches under this threshold score 0
NON_EDIBLE_MIN_KG = 1.0  # non-edible catches under this threshold score 0
# Species whose canonical name (case-insensitive) starts with any of these
# patterns score a flat 1 point per fish, regardless of weight or edible flag.
FLAT_PT_PATTERNS = ("gurnard", "catfish")  # Barbel is aliased to Catfish (White Sea)
FLAT_PT_VALUE = 1.0


def floor2(x: float) -> float:
    """Round DOWN to 2 decimal places."""
    return math.floor(float(x) * 100) / 100.0

DEFAULT_ANGLER_COLS = ["wp_no", "sasaa_no", "first_name", "surname", "club",
                       "sub_team", "league_division", "league_code"]
DEFAULT_COMP_COLS = ["comp_id", "date", "venue"]
DEFAULT_CATCH_COLS = ["comp_id", "wp_no", "species_raw", "length_cm"]

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
DIVISION_CODES = list(DIVISIONS.keys())
DIVISION_LABELS = [f"{c} — {DIVISIONS[c]}" for c in DIVISION_CODES]


def division_label(code: str) -> str:
    code = (code or "").strip().upper()
    return f"{code} — {DIVISIONS[code]}" if code in DIVISIONS else ""


def division_code(label: str) -> str:
    if not label: return ""
    return label.split(" — ", 1)[0].strip().upper()


# ---- Season management ---------------------------------------------------

def _ensure_seasons_dir() -> None:
    SEASONS_DIR.mkdir(parents=True, exist_ok=True)


def list_seasons() -> list[str]:
    _ensure_seasons_dir()
    return sorted(p.name for p in SEASONS_DIR.iterdir() if p.is_dir())


def get_active_season() -> str:
    _ensure_seasons_dir()
    if ACTIVE_FILE.exists():
        s = ACTIVE_FILE.read_text(encoding="utf-8").strip()
        if s and (SEASONS_DIR / s).exists():
            return s
    seasons = list_seasons()
    if seasons:
        ACTIVE_FILE.write_text(seasons[0], encoding="utf-8")
        return seasons[0]
    return create_season("2025-26", carry_anglers_from=None)


def set_active_season(season: str) -> None:
    if not (SEASONS_DIR / season).exists():
        raise ValueError(f"Season '{season}' does not exist")
    ACTIVE_FILE.write_text(season, encoding="utf-8")


def season_dir(season: str | None = None) -> Path:
    s = season or get_active_season()
    return SEASONS_DIR / s


def create_season(season: str, *, carry_anglers_from: str | None) -> str:
    season = season.strip()
    if not season:
        raise ValueError("Season label cannot be empty")
    if not re.match(r"^[A-Za-z0-9_\-]+$", season):
        raise ValueError("Use letters, numbers, '-' or '_' only (e.g. 2026-27)")
    target = SEASONS_DIR / season
    if target.exists():
        raise ValueError(f"Season '{season}' already exists")
    target.mkdir(parents=True)

    # anglers
    if carry_anglers_from and (SEASONS_DIR / carry_anglers_from / "anglers.csv").exists():
        shutil.copy(SEASONS_DIR / carry_anglers_from / "anglers.csv", target / "anglers.csv")
    else:
        pd.DataFrame(columns=DEFAULT_ANGLER_COLS).to_csv(target / "anglers.csv", index=False)
    # comps + catches always start empty
    pd.DataFrame(columns=DEFAULT_COMP_COLS).to_csv(target / "competitions.csv", index=False)
    pd.DataFrame(columns=DEFAULT_CATCH_COLS).to_csv(target / "catches_raw.csv", index=False)
    pd.DataFrame(columns=["comp_id", "wp_no", "species_raw", "canonical_species",
                          "length_cm", "weight_kg", "edible", "status"]
                 ).to_csv(target / "catches_scored.csv", index=False)
    return season


def delete_season(season: str) -> None:
    target = SEASONS_DIR / season
    if not target.exists():
        return
    shutil.rmtree(target)
    if get_active_season() == season:
        remaining = list_seasons()
        if remaining:
            set_active_season(remaining[0])
        else:
            ACTIVE_FILE.unlink(missing_ok=True)


def clear_catches(season: str | None = None) -> None:
    d = season_dir(season)
    pd.DataFrame(columns=DEFAULT_CATCH_COLS).to_csv(d / "catches_raw.csv", index=False)
    pd.DataFrame(columns=["comp_id", "wp_no", "species_raw", "canonical_species",
                          "length_cm", "weight_kg", "edible", "status"]
                 ).to_csv(d / "catches_scored.csv", index=False)
    (d / "team_assignments.csv").unlink(missing_ok=True)


def clear_all_season_data(season: str | None = None) -> None:
    """Wipe anglers, competitions and catches for the given season. Species master untouched."""
    d = season_dir(season)
    pd.DataFrame(columns=DEFAULT_ANGLER_COLS).to_csv(d / "anglers.csv", index=False)
    pd.DataFrame(columns=DEFAULT_COMP_COLS).to_csv(d / "competitions.csv", index=False)
    clear_catches(season)


# ---- File paths (active season) ------------------------------------------

def anglers_csv() -> Path: return season_dir() / "anglers.csv"
def comps_csv() -> Path: return season_dir() / "competitions.csv"
def catches_raw_csv() -> Path: return season_dir() / "catches_raw.csv"
def catches_scored_csv() -> Path: return season_dir() / "catches_scored.csv"
def team_assignments_csv() -> Path: return season_dir() / "team_assignments.csv"
def trophy_nominees_csv() -> Path: return season_dir() / "trophy_nominees.csv"


# ---- Trophy nominees -----------------------------------------------------

NOMINEE_COLS = ["trophy", "comp_id", "club", "wp_no"]

def load_trophy_nominees() -> pd.DataFrame:
    p = trophy_nominees_csv()
    if not p.exists():
        return pd.DataFrame(columns=NOMINEE_COLS)
    df = pd.read_csv(p, dtype=str).fillna("")
    for c in NOMINEE_COLS:
        if c not in df.columns: df[c] = ""
    return df[NOMINEE_COLS]


def save_trophy_nominees(df: pd.DataFrame) -> None:
    df = df.copy()
    for c in NOMINEE_COLS:
        if c not in df.columns: df[c] = ""
    df = df[NOMINEE_COLS]
    for c in NOMINEE_COLS:
        df[c] = df[c].astype(str).str.strip()
    df = df[(df["trophy"] != "") & (df["wp_no"] != "")]
    df = df.drop_duplicates(NOMINEE_COLS).reset_index(drop=True)
    df.to_csv(trophy_nominees_csv(), index=False)


# ---- Per-competition team assignments ------------------------------------

def load_team_assignments() -> pd.DataFrame:
    p = team_assignments_csv()
    if not p.exists():
        return pd.DataFrame(columns=["comp_id", "wp_no", "sub_team"])
    df = pd.read_csv(p, dtype=str).fillna("")
    df["comp_id"] = df["comp_id"].str.strip()
    df["wp_no"] = df["wp_no"].str.strip()
    df["sub_team"] = df["sub_team"].str.strip().str.upper()
    return df


def save_team_assignments(df: pd.DataFrame) -> None:
    df = df.copy()
    df["comp_id"] = df["comp_id"].astype(str).str.strip()
    df["wp_no"] = df["wp_no"].astype(str).str.strip()
    df["sub_team"] = df["sub_team"].astype(str).str.strip().str.upper()
    df = df[(df["comp_id"] != "") & (df["wp_no"] != "") & (df["sub_team"] != "")]
    df = df[["comp_id", "wp_no", "sub_team"]].drop_duplicates(["comp_id", "wp_no"], keep="last")
    df.to_csv(team_assignments_csv(), index=False)


def resolve_sub_team(catches: pd.DataFrame, anglers: pd.DataFrame) -> pd.DataFrame:
    """Add a 'sub_team' column to catches, using per-comp assignments where set,
    falling back to the angler's default sub_team."""
    out = catches.copy()
    ta = load_team_assignments()
    if not ta.empty:
        out = out.merge(ta.rename(columns={"sub_team": "sub_team_assigned"}),
                        on=["comp_id", "wp_no"], how="left")
    else:
        out["sub_team_assigned"] = ""
    out = out.merge(
        anglers[["wp_no", "sub_team"]].rename(columns={"sub_team": "sub_team_default"}),
        on="wp_no", how="left",
    )
    assigned = out["sub_team_assigned"].fillna("").astype(str).str.upper().str.strip()
    default = out["sub_team_default"].fillna("").astype(str).str.upper().str.strip()
    out["sub_team"] = assigned.where(assigned != "", default)
    return out.drop(columns=["sub_team_assigned", "sub_team_default"], errors="ignore")


# ---- Scoring -------------------------------------------------------------

def is_flat_pt_species(canonical: str | None) -> bool:
    if not canonical:
        return False
    n = str(canonical).strip().lower()
    return any(n.startswith(p) for p in FLAT_PT_PATTERNS)


def points_for(weight_kg: float, edible: str, canonical: str | None = None) -> float:
    """Compute points for a catch.

    Rules (in order of precedence):
      1. Gurnards / Barbel → flat 1 point per fish (overrides weight + edible).
      2. Edible < 0.5 kg → 0 points.
      3. Non-edible < 1 kg → 0 points.
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
    return Scorer()


def species_choices() -> list[str]:
    s = get_scorer()
    return sorted(s.aliases.keys()) + sorted(s.species.index.tolist())


# ---- Data IO -------------------------------------------------------------

def _read_csv(path: Path, cols: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(path, dtype=str).fillna("")
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols]


def load_anglers() -> pd.DataFrame:
    df = _read_csv(anglers_csv(), DEFAULT_ANGLER_COLS)
    df["wp_no"] = df["wp_no"].str.strip()
    return df


def save_anglers(df: pd.DataFrame) -> None:
    df = df.copy()
    df["wp_no"] = df["wp_no"].astype(str).str.strip()
    df = df[df["wp_no"] != ""].reset_index(drop=True)
    for c in DEFAULT_ANGLER_COLS:
        if c not in df.columns: df[c] = ""
    df[DEFAULT_ANGLER_COLS].to_csv(anglers_csv(), index=False)


def load_comps() -> pd.DataFrame:
    return _read_csv(comps_csv(), DEFAULT_COMP_COLS)


def save_comps(df: pd.DataFrame) -> None:
    df = df.copy()
    df["comp_id"] = df["comp_id"].astype(str).str.strip()
    df = df[df["comp_id"] != ""].reset_index(drop=True)
    for c in DEFAULT_COMP_COLS:
        if c not in df.columns: df[c] = ""
    df[DEFAULT_COMP_COLS].to_csv(comps_csv(), index=False)


def load_catches_raw() -> pd.DataFrame:
    df = _read_csv(catches_raw_csv(), DEFAULT_CATCH_COLS)
    df["wp_no"] = df["wp_no"].str.strip()
    df["comp_id"] = df["comp_id"].str.strip()
    return df


def save_catches_raw(df: pd.DataFrame) -> None:
    df = df.copy()
    for c in DEFAULT_CATCH_COLS:
        if c not in df.columns: df[c] = ""
    df = df[DEFAULT_CATCH_COLS]
    df["wp_no"] = df["wp_no"].astype(str).str.strip()
    df["comp_id"] = df["comp_id"].astype(str).str.strip()
    df["species_raw"] = df["species_raw"].astype(str).str.strip()
    df = df[(df["wp_no"] != "") & (df["comp_id"] != "") & (df["species_raw"] != "")].reset_index(drop=True)
    df.to_csv(catches_raw_csv(), index=False)
    rescore_all()


def rescore_all() -> pd.DataFrame:
    scorer = get_scorer()
    raw_path = catches_raw_csv()
    raw = pd.read_csv(raw_path, dtype=str).fillna("") if raw_path.exists() else pd.DataFrame(columns=DEFAULT_CATCH_COLS)
    rows = []
    for _, r in raw.iterrows():
        try:
            L = float(r["length_cm"]) if r["length_cm"] not in ("", None) else None
        except (TypeError, ValueError):
            L = None
        res = scorer.score(r["species_raw"], L)
        rows.append({
            "comp_id": r["comp_id"], "wp_no": r["wp_no"],
            "species_raw": r["species_raw"],
            "canonical_species": res.canonical_name,
            "length_cm": L, "weight_kg": floor2(res.weight_kg),
            "edible": res.edible, "status": res.note,
        })
    df = pd.DataFrame(rows)
    df.to_csv(catches_scored_csv(), index=False)
    return df


def load_catches_scored() -> pd.DataFrame:
    if not catches_scored_csv().exists():
        rescore_all()
    df = pd.read_csv(catches_scored_csv())
    if df.empty:
        df["points"] = []
        return df
    df["wp_no"] = df["wp_no"].astype(str).str.strip()
    df["comp_id"] = df["comp_id"].astype(str).str.strip()
    df["points"] = df.apply(
        lambda r: points_for(r["weight_kg"], r["edible"], r.get("canonical_species")),
        axis=1,
    )
    return df


def comp_options() -> list[str]:
    return load_comps()["comp_id"].dropna().astype(str).str.strip().tolist()


def angler_options() -> list[str]:
    a = load_anglers()
    return [f"{r.wp_no} — {r.first_name} {r.surname}" for r in a.itertuples()]


def parse_wp_from_label(label: str) -> str:
    return label.split(" — ", 1)[0].strip() if label else ""


# ---- Logo management -----------------------------------------------------

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


def render_season_sidebar() -> str:
    """Sidebar widget shown on every page — switches the active season."""
    active = get_active_season()
    with st.sidebar:
        st.markdown("### Season")
        seasons = list_seasons()
        idx = seasons.index(active) if active in seasons else 0
        pick = st.selectbox("Active", seasons, index=idx, key="_season_sidebar")
        if pick != active:
            set_active_season(pick)
            st.rerun()
        st.caption("Switch / create / clear on **Settings**.")
    return pick
