"""Standings calculations — best-N-of-M with drop-lowest, plus consistency ranking.

Pure functions, no Streamlit. Reusable across pages and exports.

Key concepts:
- A "score row" is per (entity, comp) — the entity is angler (wp_no) or club.
- best_n: for each entity, sort their per-comp scores ascending; if there are
  more than N, drop the LOWEST scores so only the best N count toward the total.
  Returns the per-comp matrix plus a dropped-mask matrix and a total column.
- consistency_ranking: ranks anglers per comp by points (1 = best), drops the
  WORST rank for each angler (highest number), averages the remaining.
  Lower average = more consistent.
"""
from __future__ import annotations

import pandas as pd

BEST_N_DEFAULT = 7
TOTAL_COMPS_DEFAULT = 8


def per_entity_per_comp(scored: pd.DataFrame, entity_col: str,
                        comp_order: list[str]) -> pd.DataFrame:
    """Pivot scored catches → entity × comp_id matrix of points (sum)."""
    if scored.empty:
        return pd.DataFrame(columns=[entity_col] + list(comp_order))
    p = scored.pivot_table(index=entity_col, columns="comp_id", values="points",
                           aggfunc="sum", fill_value=0)
    p = p.reindex(columns=comp_order, fill_value=0)
    return p


def apply_best_n(matrix: pd.DataFrame, n: int = BEST_N_DEFAULT
                 ) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Given an entity × comp matrix of points, return:
        (kept_matrix, dropped_mask, total_series).

    kept_matrix: same shape, but values that were dropped are unchanged
                 (we still display them — the mask shows what's struck through).
    dropped_mask: bool DataFrame, True where the cell was DROPPED (not in best n).
    total_series: sum of the kept (best n) cells, indexed by entity.

    If a row has <= n non-zero comps, nothing is dropped (drop only when there
    are strictly more contributing comps than n).
    """
    if matrix.empty or matrix.shape[1] <= n:
        return matrix, pd.DataFrame(False, index=matrix.index, columns=matrix.columns), \
               matrix.sum(axis=1) if not matrix.empty else pd.Series(dtype=float)

    dropped = pd.DataFrame(False, index=matrix.index, columns=matrix.columns)
    totals = []
    for entity, row in matrix.iterrows():
        # Sort comps for this entity by points ascending; drop the lowest until n remain.
        sorted_comps = row.sort_values(ascending=True, kind="stable")
        drop_count = max(0, len(sorted_comps) - n)
        drop_cols = sorted_comps.index[:drop_count].tolist()
        dropped.loc[entity, drop_cols] = True
        kept_sum = row[~dropped.loc[entity]].sum()
        totals.append(kept_sum)
    total = pd.Series(totals, index=matrix.index, name="total")
    return matrix, dropped, total


def best_n_table(scored: pd.DataFrame, entity_col: str, comp_order: list[str],
                 n: int = BEST_N_DEFAULT) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convenience wrapper: returns (display_df, dropped_mask).

    display_df has columns [entity_col, *comp_order, "Total"], sorted by Total desc,
    with a "Rank" column inserted at the front.
    dropped_mask is aligned to display_df rows and the comp columns.
    """
    matrix = per_entity_per_comp(scored, entity_col, comp_order)
    matrix, dropped, total = apply_best_n(matrix, n=n)
    if matrix.empty:
        empty = pd.DataFrame(columns=["Rank", entity_col, *comp_order, "Total"])
        return empty, pd.DataFrame()
    out = matrix.copy()
    out["Total"] = total
    out = out.sort_values("Total", ascending=False).reset_index()
    out.insert(0, "Rank", range(1, len(out) + 1))
    dropped = dropped.reindex(out[entity_col]).reset_index(drop=True)
    return out, dropped


def style_dropped(df: pd.DataFrame, dropped_mask: pd.DataFrame,
                  comp_cols: list[str]):
    """Return a pandas Styler that strikes through dropped cells."""
    def _style(_):
        styles = pd.DataFrame("", index=df.index, columns=df.columns)
        if dropped_mask.empty:
            return styles
        m = dropped_mask.reindex(index=df.index, columns=comp_cols, fill_value=False)
        for c in comp_cols:
            styles.loc[m[c].values, c] = (
                "text-decoration: line-through; color: #b0b0b0; "
                "background-color: #f6f6f6;"
            )
        return styles
    return df.style.apply(_style, axis=None).format(
        {c: "{:.2f}" for c in comp_cols + (["Total"] if "Total" in df.columns else [])})


# ---- Consistency ranking (Blue Ray Trophy) -------------------------------

def consistency_ranking(scored: pd.DataFrame, comp_order: list[str],
                        n: int = BEST_N_DEFAULT,
                        total_comps: int = TOTAL_COMPS_DEFAULT
                        ) -> pd.DataFrame:
    """Rank anglers by AVERAGE position rank, after dropping their WORST rank.

    Per comp: rank by points desc (1 = best). Anglers who didn't fish a comp
    get a rank equal to (number of anglers in that comp) + 1, i.e. they sit
    BELOW everyone who did fish — that comp counts against them and is the
    most likely "worst rank" to be dropped.

    For each angler:
        - drop the worst (highest) rank
        - average the remaining (n) ranks
        - lower average = more consistent

    Returns: DataFrame with columns
        wp_no, *comp_order (as ranks), Dropped (comp_id), Avg, Pos.
    """
    if scored.empty or not comp_order:
        return pd.DataFrame(columns=["wp_no", *comp_order, "Dropped", "Avg", "Pos."])

    pts = (scored.groupby(["wp_no", "comp_id"])["points"].sum()
           .unstack("comp_id").reindex(columns=comp_order))

    # Per-comp dense rank (1 = highest points). NaN where angler didn't fish.
    ranks = pts.rank(method="min", ascending=False)

    # Anglers who didn't fish a comp → rank = (count of fishers + 1)
    for c in comp_order:
        no_fish_rank = pts[c].notna().sum() + 1
        ranks[c] = ranks[c].fillna(no_fish_rank)

    # Drop worst rank (highest number). If we have fewer than n+1 comps, drop nothing.
    drop_n = max(0, len(comp_order) - n)
    out_rows = []
    for wp, row in ranks.iterrows():
        sorted_comps = row.sort_values(ascending=False, kind="stable")  # worst first
        drop_cols = sorted_comps.index[:drop_n].tolist()
        kept = row.drop(labels=drop_cols)
        avg = kept.mean()
        rec = {"wp_no": wp}
        for c in comp_order:
            rec[c] = row[c]
        rec["Dropped"] = ", ".join(drop_cols) if drop_cols else ""
        rec["Avg"] = round(float(avg), 3)
        out_rows.append(rec)

    df = pd.DataFrame(out_rows).sort_values("Avg", ascending=True).reset_index(drop=True)
    df.insert(0, "Pos.", range(1, len(df) + 1))
    return df
