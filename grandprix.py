"""Grand Prix scoring engine (Phase 1, trial).

Pure functions, no Streamlit. Builds on standings.per_entity_per_comp /
apply_best_n so the GP model reuses the exact weight-point basis the league
already trusts.

GP model (proposal Version A):
    GP(angler, IC) = weight_points(angler, IC) / max_weight_points(IC) * gp_max
where gp_max defaults to 50. The "max" can be taken over the whole field
(pool="overall") or within each division (pool="division").

Optional work-rate layer ("+1 per fish"): +1 per qualifying catch (meets
minimum weight, i.e. weight-points > 0, excluding sight fish), added AFTER GP
conversion (uncapped) per the committee decision 2026-06-05.

Drop-worst is supported via standings.apply_best_n on the per-IC value matrix.
"""
from __future__ import annotations

import pandas as pd

from standings import apply_best_n, per_entity_per_comp

GP_MAX_DEFAULT = 50.0


def _is_sight(species: str) -> bool:
    s = str(species or "").lower()
    return "site fish" in s or "sight fish" in s or "gurnard" in s


def weight_matrix(scored: pd.DataFrame, comp_order: list[str]) -> pd.DataFrame:
    """entity(wp_no) × comp matrix of weight points (reuses existing engine)."""
    return per_entity_per_comp(scored, "wp_no", comp_order)


def to_gp(matrix: pd.DataFrame, *, gp_max: float = GP_MAX_DEFAULT,
          groups: dict[str, str] | None = None) -> pd.DataFrame:
    """Convert a weight-point matrix to GP points.

    groups: optional {entity -> group} (e.g. wp_no -> division). When given,
    the per-IC max is computed WITHIN each group, so each division has its own
    50-point benchmark. When None, the max is over the whole field.
    """
    if matrix.empty:
        return matrix
    out = matrix.astype(float).copy()
    if not groups:
        for c in out.columns:
            m = out[c].max()
            out[c] = (out[c] / m * gp_max) if m and m > 0 else 0.0
        return out
    # per-group normalisation
    grp = pd.Series({e: groups.get(e, "") for e in out.index})
    for g, ents in grp.groupby(grp).groups.items():
        sub = out.loc[ents]
        for c in out.columns:
            m = sub[c].max()
            out.loc[ents, c] = (sub[c] / m * gp_max) if m and m > 0 else 0.0
    return out


def fish_count_matrix(scored: pd.DataFrame, comp_order: list[str]) -> pd.DataFrame:
    """entity × comp matrix of qualifying-fish counts (weight-points > 0, not sight)."""
    if scored.empty:
        return pd.DataFrame(index=pd.Index([], name="wp_no"), columns=comp_order).fillna(0)
    df = scored.copy()
    df["_pts"] = pd.to_numeric(df.get("points", 0), errors="coerce").fillna(0.0)
    df["_qual"] = (df["_pts"] > 0) & (~df["canonical_species"].map(_is_sight))
    q = df[df["_qual"]]
    if q.empty:
        return pd.DataFrame(0.0, index=scored["wp_no"].unique(), columns=comp_order)
    m = (q.pivot_table(index="wp_no", columns="comp_id", values="_qual",
                       aggfunc="size", fill_value=0)
           .reindex(columns=comp_order, fill_value=0))
    return m.astype(float)


def gp_standings(scored: pd.DataFrame, anglers: pd.DataFrame, comp_order: list[str],
                 *, gp_max: float = GP_MAX_DEFAULT, drop_worst: bool = False,
                 best_n: int = 7, pool: str = "overall",
                 add_fish: bool = False) -> pd.DataFrame:
    """Return ranked GP standings.

    Columns: Rank, wp_no, Angler, Club, Div, GP, [Fish, GP+Fish], Weight,
             ICs_scored, ICs_blobbed, *per-IC GP columns.
    Sorted by the headline metric (GP+Fish if add_fish else GP), descending.
    """
    cols_meta = ["wp_no", "first_name", "surname", "club", "league_code"]
    meta = (anglers[cols_meta].drop_duplicates("wp_no").set_index("wp_no")
            if not anglers.empty else pd.DataFrame(columns=cols_meta).set_index("wp_no"))

    wmat = weight_matrix(scored, comp_order)
    if wmat.empty:
        return pd.DataFrame(columns=["Rank", "wp_no", "Angler", "Club", "Div",
                                     "GP", "Weight", "ICs_scored", "ICs_blobbed"])

    groups = None
    if pool == "division":
        groups = {wp: str(meta.loc[wp, "league_code"]) if wp in meta.index else ""
                  for wp in wmat.index}

    gpmat = to_gp(wmat, gp_max=gp_max, groups=groups)

    # per-IC value matrix used for ranking (GP, optionally + fish)
    val = gpmat.copy()
    fishmat = None
    if add_fish:
        fishmat = fish_count_matrix(scored, comp_order).reindex(
            index=gpmat.index, columns=comp_order, fill_value=0)
        val = gpmat.add(fishmat, fill_value=0)

    if drop_worst:
        _, _, total = apply_best_n(val, n=best_n)
    else:
        total = val.sum(axis=1)

    weight_total = wmat.sum(axis=1)
    gp_total = gpmat.sum(axis=1)
    ics_scored = (wmat > 0).sum(axis=1)
    ics_blobbed = (wmat <= 0).sum(axis=1)

    out = pd.DataFrame(index=wmat.index)
    out["Headline"] = total
    out["GP"] = gp_total.round(2)
    if add_fish:
        out["Fish"] = fishmat.sum(axis=1).astype(int)
        out["GP+Fish"] = total.round(2)
    out["Weight"] = weight_total.round(2)
    out["ICs_scored"] = ics_scored
    out["ICs_blobbed"] = ics_blobbed
    # attach per-IC GP columns
    for c in comp_order:
        out[f"IC{c}"] = gpmat[c].round(2)

    out = out.join(meta, how="left")
    out["Angler"] = (out["first_name"].fillna("") + " " + out["surname"].fillna("")).str.strip()
    out["Angler"] = out["Angler"].replace("", "(unknown)")
    out = out.rename(columns={"club": "Club", "league_code": "Div"})

    out = out.sort_values("Headline", ascending=False).reset_index()
    out.insert(0, "Rank", range(1, len(out) + 1))

    lead = ["Rank", "wp_no", "Angler", "Club", "Div", "GP"]
    if add_fish:
        lead += ["Fish", "GP+Fish"]
    lead += ["Weight", "ICs_scored", "ICs_blobbed"]
    ic_cols = [f"IC{c}" for c in comp_order]
    return out[lead + ic_cols]


def weight_vs_gp(scored: pd.DataFrame, anglers: pd.DataFrame, comp_order: list[str],
                 *, gp_max: float = GP_MAX_DEFAULT, drop_worst: bool = False,
                 best_n: int = 7, pool: str = "overall", add_fish: bool = False,
                 top: int = 25) -> pd.DataFrame:
    """Comparison frame for the butterfly chart: weight rank vs GP rank, top-N by weight."""
    gp = gp_standings(scored, anglers, comp_order, gp_max=gp_max,
                      drop_worst=drop_worst, best_n=best_n, pool=pool, add_fish=add_fish)
    if gp.empty:
        return gp
    gp = gp.rename(columns={"Rank": "GP_rank"})
    gp = gp.sort_values("Weight", ascending=False).reset_index(drop=True)
    gp.insert(0, "Weight_rank", range(1, len(gp) + 1))
    gp["Move"] = gp["Weight_rank"] - gp["GP_rank"]   # +ve = moved up under GP
    return gp.head(top)
