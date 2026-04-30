"""Analytics layer — dataset registry + chart renderer.

Pure data + plotting helpers. Reuses existing aggregation logic from
trophies.py / standings.py — no duplicate maths.

Public API:
    DATASETS                    -> registry of available datasets
    get_leaderboard_data(...)   -> returns ranked DataFrame for a dataset
    render_chart(data, ...)     -> returns a Plotly Figure

A "dataset" is an aggregation shape (cat, value) ready to plot or table.
"""
from __future__ import annotations

import site
import sys

import pandas as pd

try:
    import plotly.express as px  # noqa: F401
except ModuleNotFoundError:
    usp = site.getusersitepackages()
    paths = usp if isinstance(usp, list) else [usp]
    for p in paths:
        if p and p not in sys.path:
            sys.path.insert(0, p)

import plotly.express as px

from standings import apply_best_n, per_entity_per_comp
from trophies import _enrich  # internal helper — single source of enrichment


# Each dataset is described as (label, kind, value_label) where kind tells
# the renderer how to interpret the data:
#   - "ranking": one row per category, value column = "Value"
#   - "trend":   one row per (category, comp_id) — line-chart friendly
DATASETS: dict[str, dict] = {
    "Heaviest Edible":          {"kind": "ranking", "value_label": "Weight (kg)",
                                  "category_label": "Catch"},
    "Heaviest Non-Edible":      {"kind": "ranking", "value_label": "Weight (kg)",
                                  "category_label": "Catch"},
    "Most Edibles per Club":    {"kind": "ranking", "value_label": "Edible catches",
                                  "category_label": "Club"},
    "Most Non-Edibles per Club":{"kind": "ranking", "value_label": "Non-edible catches",
                                  "category_label": "Club"},
    "Most Fish per Angler":     {"kind": "ranking", "value_label": "Catches",
                                  "category_label": "Angler"},
    "Overall Points per Angler":{"kind": "ranking", "value_label": "Points",
                                  "category_label": "Angler"},
    "Club Standings":           {"kind": "ranking", "value_label": "Points",
                                  "category_label": "Club"},
}


def get_leaderboard_data(dataset: str, scored: pd.DataFrame,
                         anglers: pd.DataFrame, *,
                         top_n: int | None = None,
                         comp_order: list[str] | None = None,
                         best_n: int | None = None) -> pd.DataFrame:
    """Return a ranked DataFrame for the given dataset name.

    Output schema is uniform: columns are
        ["Rank", "Category", "Value", *extras]
    where Category is the entity name (catch / angler / club) and Value
    is the numeric metric. Extras provide context (Club, Lg, etc.).

    Args:
        dataset: one of DATASETS.keys()
        scored: catches_scored frame (already filtered upstream)
        anglers: anglers frame (already filtered upstream)
        top_n: trim to top N rows (default no trim)
        comp_order: needed for points-based datasets (best-N math)
        best_n: enable best-N-of-M scoring; None = sum all comps
    """
    if dataset not in DATASETS:
        raise ValueError(f"Unknown dataset: {dataset!r}")
    if scored.empty:
        return pd.DataFrame(columns=["Rank", "Category", "Value"])

    cc = _enrich(scored, anglers)
    n_eff = best_n if best_n else 10**6
    comp_order = comp_order or sorted(scored["comp_id"].astype(str).unique().tolist())

    if dataset == "Heaviest Edible":
        sub = cc[(cc["edible"] == "Y") & (cc["valid"]) & (cc["weight_kg"] > 0)]
        out = (sub.sort_values("weight_kg", ascending=False)
               [["Angler", "club", "canonical_species", "comp_id", "weight_kg"]]
               .rename(columns={"club": "Club", "canonical_species": "Species",
                                "comp_id": "Comp", "weight_kg": "Value"}))
        out["Category"] = out["Angler"] + " · " + out["Species"]

    elif dataset == "Heaviest Non-Edible":
        sub = cc[(cc["edible"] == "N") & (cc["valid"]) & (cc["weight_kg"] > 0)]
        out = (sub.sort_values("weight_kg", ascending=False)
               [["Angler", "club", "canonical_species", "comp_id", "weight_kg"]]
               .rename(columns={"club": "Club", "canonical_species": "Species",
                                "comp_id": "Comp", "weight_kg": "Value"}))
        out["Category"] = out["Angler"] + " · " + out["Species"]

    elif dataset == "Most Edibles per Club":
        sub = cc[(cc["edible"] == "Y") & (cc["valid"])]
        agg = (sub.groupby("club").size().reset_index(name="Value")
               .sort_values("Value", ascending=False))
        out = agg.rename(columns={"club": "Category"})

    elif dataset == "Most Non-Edibles per Club":
        sub = cc[(cc["edible"] == "N") & (cc["valid"])]
        agg = (sub.groupby("club").size().reset_index(name="Value")
               .sort_values("Value", ascending=False))
        out = agg.rename(columns={"club": "Category"})

    elif dataset == "Most Fish per Angler":
        sub = cc[cc["valid"]]
        agg = (sub.groupby(["wp_no", "Angler", "club", "league_code"])
               .size().reset_index(name="Value")
               .sort_values("Value", ascending=False))
        out = agg.rename(columns={"Angler": "Category", "club": "Club",
                                  "league_code": "Lg"})

    elif dataset == "Overall Points per Angler":
        matrix = per_entity_per_comp(cc, "wp_no", comp_order)
        _, _, total = apply_best_n(matrix, n=n_eff)
        meta = cc.drop_duplicates("wp_no").set_index("wp_no")[
            ["Angler", "club", "league_code"]]
        out = (total.to_frame("Value").join(meta).reset_index()
               .sort_values("Value", ascending=False))
        out = out.rename(columns={"Angler": "Category", "club": "Club",
                                  "league_code": "Lg"})

    elif dataset == "Club Standings":
        matrix = per_entity_per_comp(cc, "club", comp_order)
        _, _, total = apply_best_n(matrix, n=n_eff)
        out = (total.to_frame("Value").reset_index()
               .rename(columns={"club": "Category"})
               .sort_values("Value", ascending=False))
    else:
        raise ValueError(f"Unhandled dataset: {dataset!r}")

    out = out.reset_index(drop=True)
    out.insert(0, "Rank", range(1, len(out) + 1))
    if top_n is not None:
        out = out.head(top_n).reset_index(drop=True)
    return out


def get_trend_data(dataset: str, scored: pd.DataFrame, anglers: pd.DataFrame, *,
                   top_n: int | None = None,
                   comp_order: list[str] | None = None) -> pd.DataFrame:
    """Long-format frame for line charts: columns = [Category, Comp, Value].

    Currently supports:
        - "Overall Points per Angler" -> per-comp points for top-N anglers
        - "Club Standings"            -> per-comp points per club
    Other datasets are flattened by replicating the ranking value across comps,
    which is a degenerate line chart — caller should prefer bar/pie for those.
    """
    cc = _enrich(scored, anglers)
    if cc.empty:
        return pd.DataFrame(columns=["Category", "Comp", "Value"])
    comp_order = comp_order or sorted(scored["comp_id"].astype(str).unique().tolist())

    if dataset == "Overall Points per Angler":
        ranking = get_leaderboard_data(dataset, scored, anglers,
                                        top_n=top_n, comp_order=comp_order)
        keep = ranking["Category"].tolist()
        long = (cc.groupby(["Angler", "comp_id"])["points"].sum()
                .reset_index()
                .rename(columns={"Angler": "Category", "comp_id": "Comp",
                                 "points": "Value"}))
        long = long[long["Category"].isin(keep)]
        long["Comp"] = pd.Categorical(long["Comp"], categories=comp_order, ordered=True)
        return long.sort_values(["Category", "Comp"])

    if dataset == "Club Standings":
        long = (cc.groupby(["club", "comp_id"])["points"].sum()
                .reset_index()
                .rename(columns={"club": "Category", "comp_id": "Comp",
                                 "points": "Value"}))
        long["Comp"] = pd.Categorical(long["Comp"], categories=comp_order, ordered=True)
        return long.sort_values(["Category", "Comp"])

    if dataset in ("Most Edibles per Club", "Most Non-Edibles per Club"):
        edible = "Y" if dataset == "Most Edibles per Club" else "N"
        sub = cc[(cc["edible"] == edible) & (cc["valid"])]
        long = (sub.groupby(["club", "comp_id"]).size()
                .reset_index(name="Value")
                .rename(columns={"club": "Category", "comp_id": "Comp"}))
        long["Comp"] = pd.Categorical(long["Comp"], categories=comp_order, ordered=True)
        return long.sort_values(["Category", "Comp"])

    if dataset == "Most Fish per Angler":
        sub = cc[cc["valid"]]
        ranking = get_leaderboard_data(dataset, scored, anglers,
                                        top_n=top_n, comp_order=comp_order)
        keep = ranking["Category"].tolist()
        long = (sub.groupby(["Angler", "comp_id"]).size()
                .reset_index(name="Value")
                .rename(columns={"Angler": "Category", "comp_id": "Comp"}))
        long = long[long["Category"].isin(keep)]
        long["Comp"] = pd.Categorical(long["Comp"], categories=comp_order, ordered=True)
        return long.sort_values(["Category", "Comp"])

    # Heaviest Edible / Non-Edible — single catches don't have a meaningful
    # trend; fall back to flat single-point series (caller should pick bar/pie).
    rk = get_leaderboard_data(dataset, scored, anglers,
                               top_n=top_n, comp_order=comp_order)
    long = rk[["Category", "Comp", "Value"]].copy() if "Comp" in rk.columns \
        else rk[["Category", "Value"]].assign(Comp="")
    return long


def render_chart(data: pd.DataFrame, chart_type: str, *, title: str = "",
                 value_label: str = "Value", category_label: str = "Category"):
    """Return a Plotly Figure for the given DataFrame, styled with the active theme.

    For chart_type == "Line", `data` must be long-format with a Comp column.
    Bar / Pie operate on flat (Category, Value) data.
    """
    from theme import chart_palette, load_theme, plotly_layout
    theme = load_theme()
    palette = chart_palette(theme)
    primary, accent = theme["chart_primary"], theme["chart_accent"]

    if data is None or data.empty:
        fig = px.bar(title=f"{title} — no data")
        fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), height=420,
                          **plotly_layout(theme))
        return fig

    chart_type = chart_type.lower()

    if chart_type == "pie":
        fig = px.pie(data, names="Category", values="Value", hole=0.35,
                     title=title, color_discrete_sequence=palette)
        fig.update_traces(textposition="inside", textinfo="percent+label",
                          hovertemplate="%{label}: %{value:.2f}<extra></extra>")
    elif chart_type == "line":
        if "Comp" not in data.columns:
            fig = px.line(data, x="Category", y="Value", markers=True,
                          title=title, color_discrete_sequence=palette)
        else:
            fig = px.line(data, x="Comp", y="Value", color="Category",
                          markers=True, title=title,
                          color_discrete_sequence=palette)
        fig.update_layout(xaxis_title="Competition", yaxis_title=value_label,
                          hovermode="x unified")
    else:  # default = bar
        fig = px.bar(data, x="Category", y="Value", text="Value",
                     color="Value",
                     color_continuous_scale=[[0, primary], [1, accent]],
                     title=title)
        fig.update_traces(texttemplate="%{text:.2f}", textposition="outside",
                          hovertemplate=f"%{{x}}<br>{value_label}: %{{y:.2f}}<extra></extra>")
        fig.update_layout(xaxis_title=category_label, yaxis_title=value_label,
                          coloraxis_showscale=False)

    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), height=480,
                      **plotly_layout(theme))
    return fig
