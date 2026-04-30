"""Trophy logic — pure functions over scored catches + roster.

Each function returns a small DataFrame ready to render. None of these
write to disk or touch Streamlit; they're called from pages/8_Trophies.py.

Trophy → function mapping:
    Masters-Four              -> masters_four(...)
    Sir Drummond Chapman      -> sir_drummond_chapman(...)   (uses nominees)
    Wallace van Wyk           -> wallace_van_wyk(...)        (Team A, Feb interclub)
    Piet Alberts              -> piet_alberts(...)           (Junior, lowest comp_id)
    Blue Ray                  -> blue_ray(...)               (consistency)
    Radio Good Hope           -> radio_good_hope(...)        (most edibles per club)
    Mario Texeira             -> mario_texeira(...)          (heaviest edible)
    Station Motors            -> station_motors(...)         (heaviest non-edible)
    Mutual                    -> champion_division(..., "J", "K")  (Junior/Kids)
    Syfie Douglas             -> champion_division(..., "L")
    Willie Morries            -> champion_division(..., "M")
    NJ van As                 -> nj_van_as(...)              (overall champion)
"""
from __future__ import annotations

import pandas as pd

from standings import (BEST_N_DEFAULT, apply_best_n, consistency_ranking,
                       per_entity_per_comp)


# ---- Helpers -------------------------------------------------------------

def _enrich(scored: pd.DataFrame, anglers: pd.DataFrame) -> pd.DataFrame:
    """Join catches with angler metadata. Returns enriched copy."""
    if scored.empty:
        return scored.assign(Angler="", club="", league_code="")
    cc = scored.merge(
        anglers[["wp_no", "first_name", "surname", "club", "league_code"]],
        on="wp_no", how="left",
    )
    cc["club"] = cc["club"].fillna("UNKNOWN").replace("", "UNKNOWN")
    cc["league_code"] = cc["league_code"].fillna("").astype(str).str.upper().str.strip()
    cc["Angler"] = (cc["first_name"].fillna("") + " " + cc["surname"].fillna("")).str.strip()
    cc.loc[cc["Angler"] == "", "Angler"] = "(unknown)"
    cc["weight_kg"] = pd.to_numeric(cc["weight_kg"], errors="coerce").fillna(0.0)
    cc["edible"] = cc["edible"].fillna("").astype(str).str.upper()
    cc["status"] = cc["status"].fillna("").astype(str)
    cc["valid"] = cc["status"].str.startswith("ok")
    return cc


def first_comp_in_month(comps: pd.DataFrame, month: int) -> str | None:
    """Return the comp_id of the earliest comp whose date falls in the given month.
    Falls back to lowest comp_id alphabetically if dates are missing.
    """
    if comps.empty:
        return None
    df = comps.copy()
    df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce")
    in_month = df[df["date_parsed"].dt.month == month]
    if in_month.empty:
        return None
    return in_month.sort_values(["date_parsed", "comp_id"]).iloc[0]["comp_id"]


def lowest_comp_id(comps: pd.DataFrame) -> str | None:
    """Return the alphabetically lowest comp_id."""
    if comps.empty:
        return None
    ids = sorted(comps["comp_id"].dropna().astype(str).str.strip().unique())
    return ids[0] if ids else None


# ---- Catch-record trophies (single winner) -------------------------------

def mario_texeira(scored: pd.DataFrame, anglers: pd.DataFrame) -> pd.DataFrame:
    """Heaviest edible — single winner."""
    cc = _enrich(scored, anglers)
    cand = cc[(cc["edible"] == "Y") & (cc["valid"]) & (cc["weight_kg"] > 0)]
    if cand.empty:
        return pd.DataFrame()
    return (cand.sort_values("weight_kg", ascending=False)
            .head(10)[["comp_id", "Angler", "club", "canonical_species",
                       "length_cm", "weight_kg", "points"]]
            .rename(columns={"comp_id": "Comp", "club": "Club",
                             "canonical_species": "Species",
                             "length_cm": "Length", "weight_kg": "Weight (kg)",
                             "points": "Pts"})
            .reset_index(drop=True))


def station_motors(scored: pd.DataFrame, anglers: pd.DataFrame) -> pd.DataFrame:
    """Heaviest non-edible — single winner."""
    cc = _enrich(scored, anglers)
    cand = cc[(cc["edible"] == "N") & (cc["valid"]) & (cc["weight_kg"] > 0)]
    if cand.empty:
        return pd.DataFrame()
    return (cand.sort_values("weight_kg", ascending=False)
            .head(10)[["comp_id", "Angler", "club", "canonical_species",
                       "length_cm", "weight_kg", "points"]]
            .rename(columns={"comp_id": "Comp", "club": "Club",
                             "canonical_species": "Species",
                             "length_cm": "Length", "weight_kg": "Weight (kg)",
                             "points": "Pts"})
            .reset_index(drop=True))


def radio_good_hope(scored: pd.DataFrame, anglers: pd.DataFrame) -> pd.DataFrame:
    """Club with most edible catches."""
    cc = _enrich(scored, anglers)
    cand = cc[(cc["edible"] == "Y") & (cc["valid"])]
    if cand.empty:
        return pd.DataFrame()
    out = (cand.groupby("club").size().reset_index(name="Edible catches")
           .sort_values("Edible catches", ascending=False).reset_index(drop=True))
    out.insert(0, "Pos.", range(1, len(out) + 1))
    return out.rename(columns={"club": "Club"})


# ---- Champion-by-division (best 7 of 8 by points) ------------------------

def champion_division(scored: pd.DataFrame, anglers: pd.DataFrame,
                      *divisions: str, comp_order: list[str],
                      n: int = BEST_N_DEFAULT) -> pd.DataFrame:
    """Return ranked anglers in the given division code(s), best-N points total.
    Pass multiple division codes for combined divisions (e.g. Mutual = J + K).
    """
    cc = _enrich(scored, anglers)
    if cc.empty or not comp_order:
        return pd.DataFrame()
    div_set = {d.upper() for d in divisions}
    sub = cc[cc["league_code"].isin(div_set)]
    if sub.empty:
        return pd.DataFrame()
    matrix = per_entity_per_comp(sub, "wp_no", comp_order)
    _, dropped, total = apply_best_n(matrix, n=n)
    out = matrix.copy(); out["Total"] = total
    meta = sub.drop_duplicates("wp_no").set_index("wp_no")[["Angler", "club", "league_code"]]
    out = out.join(meta).sort_values("Total", ascending=False).reset_index()
    out.insert(0, "Pos.", range(1, len(out) + 1))
    out = out.rename(columns={"wp_no": "WP No", "club": "Club",
                              "league_code": "Lg"})
    cols = ["Pos.", "WP No", "Angler", "Club", "Lg"] + comp_order + ["Total"]
    return out[cols]


def nj_van_as(scored: pd.DataFrame, anglers: pd.DataFrame, *,
              comp_order: list[str], n: int = BEST_N_DEFAULT) -> pd.DataFrame:
    """Overall Champion — highest total points across all divisions, best N of M."""
    cc = _enrich(scored, anglers)
    if cc.empty or not comp_order:
        return pd.DataFrame()
    matrix = per_entity_per_comp(cc, "wp_no", comp_order)
    _, _, total = apply_best_n(matrix, n=n)
    out = matrix.copy(); out["Total"] = total
    meta = cc.drop_duplicates("wp_no").set_index("wp_no")[["Angler", "club", "league_code"]]
    out = out.join(meta).sort_values("Total", ascending=False).reset_index()
    out.insert(0, "Pos.", range(1, len(out) + 1))
    out = out.rename(columns={"wp_no": "WP No", "club": "Club", "league_code": "Lg"})
    cols = ["Pos.", "WP No", "Angler", "Club", "Lg"] + comp_order + ["Total"]
    return out[cols]


# ---- Junior single-comp trophy -------------------------------------------

def piet_alberts(scored: pd.DataFrame, anglers: pd.DataFrame,
                 comp_id: str | None) -> pd.DataFrame:
    """Junior winner of the lowest-comp_id competition (J + K combined)."""
    if not comp_id:
        return pd.DataFrame()
    cc = _enrich(scored, anglers)
    sub = cc[(cc["comp_id"] == comp_id) & (cc["league_code"].isin({"J", "K"}))]
    if sub.empty:
        return pd.DataFrame()
    out = (sub.groupby(["wp_no", "Angler", "club", "league_code"])
           .agg(points=("points", "sum"),
                weight=("weight_kg", "sum"),
                catches=("comp_id", "count"))
           .reset_index()
           .sort_values(["points", "weight"], ascending=[False, False])
           .reset_index(drop=True))
    out.insert(0, "Pos.", range(1, len(out) + 1))
    out["points"] = out["points"].round(2)
    out["weight"] = out["weight"].round(2)
    return out.rename(columns={"wp_no": "WP No", "club": "Club",
                               "league_code": "Lg", "points": "Points",
                               "weight": "Total Weight (kg)",
                               "catches": "Catches"})


# ---- Masters-Four --------------------------------------------------------

def masters_four(scored: pd.DataFrame, anglers: pd.DataFrame) -> pd.DataFrame:
    """Top 4 Masters per club per competition, summed per club per comp.
    Then totalled across all comps to give the trophy ranking.
    """
    cc = _enrich(scored, anglers)
    masters = cc[cc["league_code"] == "M"]
    if masters.empty:
        return pd.DataFrame()

    # Per (club, comp, angler) total points
    per_ang = (masters.groupby(["club", "comp_id", "wp_no", "Angler"])["points"]
               .sum().reset_index())
    # Pick top 4 per (club, comp)
    top4 = (per_ang.sort_values(["club", "comp_id", "points"],
                                ascending=[True, True, False])
            .groupby(["club", "comp_id"]).head(4))
    # Sum the top-4 per (club, comp)
    per_club_comp = (top4.groupby(["club", "comp_id"])["points"]
                     .sum().reset_index(name="club_pts"))
    # Wide pivot for display
    wide = per_club_comp.pivot(index="club", columns="comp_id",
                               values="club_pts").fillna(0)
    wide["Total"] = wide.sum(axis=1)
    wide = wide.sort_values("Total", ascending=False).reset_index()
    wide.insert(0, "Pos.", range(1, len(wide) + 1))
    return wide.rename(columns={"club": "Club"})


# ---- Wallace van Wyk -----------------------------------------------------

def wallace_van_wyk(scored: pd.DataFrame, anglers: pd.DataFrame,
                    team_assignments: pd.DataFrame, *,
                    feb_comp_id: str | None) -> tuple[pd.DataFrame, str | None]:
    """Team A (8 anglers per club) competing in February Interclub only.

    Reads team_assignments to find Team A members for that comp, sums their
    points in that comp. Returns (ranking_df, feb_comp_id).
    """
    if not feb_comp_id:
        return pd.DataFrame(), None
    cc = _enrich(scored, anglers)
    sub = cc[cc["comp_id"] == feb_comp_id]
    if sub.empty or team_assignments.empty:
        return pd.DataFrame(), feb_comp_id
    ta = team_assignments[(team_assignments["comp_id"] == feb_comp_id) &
                          (team_assignments["sub_team"].str.upper() == "A")]
    if ta.empty:
        return pd.DataFrame(), feb_comp_id
    sub = sub.merge(ta[["wp_no"]], on="wp_no", how="inner")
    if sub.empty:
        return pd.DataFrame(), feb_comp_id
    out = (sub.groupby(["club"])
           .agg(team_pts=("points", "sum"),
                anglers=("wp_no", "nunique"),
                catches=("comp_id", "count"))
           .reset_index()
           .sort_values("team_pts", ascending=False).reset_index(drop=True))
    out.insert(0, "Pos.", range(1, len(out) + 1))
    out["team_pts"] = out["team_pts"].round(2)
    return out.rename(columns={"club": "Club", "team_pts": "Team Points",
                               "anglers": "Anglers in Team A",
                               "catches": "Catches"}), feb_comp_id


# ---- Sir Drummond Chapman ------------------------------------------------

def sir_drummond_chapman(scored: pd.DataFrame, anglers: pd.DataFrame,
                         nominees: pd.DataFrame, *,
                         jan_comp_id: str | None
                         ) -> tuple[pd.DataFrame, str | None]:
    """4 nominated anglers per club competing in the first January comp.

    nominees: trophy_nominees DataFrame filtered to trophy='SDC'.
    Returns (ranking_df, jan_comp_id).
    """
    if not jan_comp_id:
        return pd.DataFrame(), None
    cc = _enrich(scored, anglers)
    sub = cc[cc["comp_id"] == jan_comp_id]
    if sub.empty:
        return pd.DataFrame(), jan_comp_id

    nom = nominees[(nominees["trophy"] == "SDC") &
                   (nominees["comp_id"] == jan_comp_id)]
    if nom.empty:
        return pd.DataFrame(), jan_comp_id
    sub = sub.merge(nom[["wp_no"]], on="wp_no", how="inner")
    if sub.empty:
        return pd.DataFrame(), jan_comp_id

    out = (sub.groupby("club")
           .agg(team_pts=("points", "sum"),
                anglers=("wp_no", "nunique"),
                catches=("comp_id", "count"))
           .reset_index()
           .sort_values("team_pts", ascending=False).reset_index(drop=True))
    out.insert(0, "Pos.", range(1, len(out) + 1))
    out["team_pts"] = out["team_pts"].round(2)
    return out.rename(columns={"club": "Club", "team_pts": "Team Points",
                               "anglers": "Nominees who fished",
                               "catches": "Catches"}), jan_comp_id


# ---- Blue Ray (consistency) ---------------------------------------------

def blue_ray(scored: pd.DataFrame, anglers: pd.DataFrame, *,
             comp_order: list[str], n: int = BEST_N_DEFAULT) -> pd.DataFrame:
    """Most consistent angler — drop worst rank, average remaining ranks.
    Lower average = more consistent.
    """
    cc = _enrich(scored, anglers)
    if cc.empty or not comp_order:
        return pd.DataFrame()
    cr = consistency_ranking(cc, comp_order, n=n)
    if cr.empty:
        return cr
    meta = cc.drop_duplicates("wp_no").set_index("wp_no")[["Angler", "club", "league_code"]]
    cr = cr.merge(meta, left_on="wp_no", right_index=True, how="left")
    cr = cr.rename(columns={"wp_no": "WP No", "club": "Club", "league_code": "Lg"})
    cols = ["Pos.", "WP No", "Angler", "Club", "Lg"] + comp_order + ["Dropped", "Avg"]
    return cr[cols]
