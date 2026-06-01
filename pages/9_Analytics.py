"""Analytics — interactive charts driven by sidebar controls."""
from __future__ import annotations

import streamlit as st

from auth import require_login
require_login()

from analytics import (DATASETS, get_leaderboard_data, get_trend_data,
                       render_chart)
from app_lib import (apply_filters, highlight_leader, load_anglers,
                     load_catches_scored, load_comps, render_global_filters,
                     render_season_sidebar)
from standings import BEST_N_DEFAULT
from ui import divider_label, empty_state, leader_banner, page_header, section_label

st.set_page_config(page_title="Analytics · WCSAA League",
                   page_icon="📊", layout="wide")
active = render_season_sidebar()
page_header("Charts & Analytics",
            "Interactive data visualisations — filter in the sidebar, pick a chart below",
            "📊", active)

catches = load_catches_scored()
anglers = load_anglers()

if catches.empty:
    empty_state("No catches yet — record some on the Catches page first.", "📊")
    st.stop()

# ── Global filters ────────────────────────────────────────────────────────
filters = render_global_filters(catches, anglers)
catches_f, anglers_f = apply_filters(catches, anglers, filters)
if catches_f.empty:
    st.warning("No catches match the current filters.")
    st.stop()

# ── Main-area controls (IC + Venue + Dataset + Top-N) ────────────────────
comps_df    = load_comps()
all_comps   = sorted(catches_f["comp_id"].astype(str).unique().tolist())
all_venues  = sorted(comps_df["venue"].dropna().unique().tolist()) if not comps_df.empty else []
venue_by_id = dict(zip(comps_df["comp_id"].astype(str), comps_df["venue"])) if not comps_df.empty else {}

date_by_id  = dict(zip(comps_df["comp_id"].astype(str), comps_df["date"])) if not comps_df.empty else {}

def _ic_label(cid: str) -> str:
    parts = [f"IC {cid}"]
    if cid in date_by_id and date_by_id[cid]:
        parts.append(str(date_by_id[cid]))
    if cid in venue_by_id and venue_by_id[cid]:
        parts.append(venue_by_id[cid])
    return " · ".join(parts)

with st.container(border=True):
    section_label("Filters")
    c1, c2, c3, c4 = st.columns([3, 2, 3, 1])
    with c1:
        ic_picks = st.multiselect(
            "Competitions (IC)", all_comps,
            default=all_comps,
            format_func=_ic_label,
            key="an_ic_picks",
            help="Each selected IC is shown separately — no aggregation.")
    with c2:
        venue_picks = st.multiselect(
            "Venues", all_venues, default=all_venues, key="an_venue_picks",
            help="Each venue's catches are kept separate per IC.")
    with c3:
        dataset = st.selectbox("Dataset", list(DATASETS.keys()), key="an_dataset")
    with c4:
        top_n_raw = st.select_slider(
            "Top N", options=[5, 10, 15, 20, 30, 50, "All"],
            value=10, key="an_top_n",
            help="Pick 'All' to show every category — useful with species datasets.")
        top_n = None if top_n_raw == "All" else int(top_n_raw)

# Apply IC + venue filters (intersection — each IC remains a distinct group)
if ic_picks:
    catches_f = catches_f[catches_f["comp_id"].astype(str).isin(ic_picks)]
if venue_picks and venue_picks != all_venues:
    venue_comp_ids = {cid for cid, v in venue_by_id.items() if v in venue_picks}
    catches_f = catches_f[catches_f["comp_id"].astype(str).isin(venue_comp_ids)]

if catches_f.empty:
    st.warning("No catches match the current filters.")
    st.stop()

comp_order = sorted(catches_f["comp_id"].astype(str).unique().tolist())
st.caption(f"Showing **{len(comp_order)} competition(s)** across "
           f"**{len({venue_by_id.get(c, '?') for c in comp_order})} venue(s)** — "
           f"{len(catches_f)} catches.")

# ── Best-N toggle (sidebar) ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📊 Chart controls")
    use_best_n = st.toggle(
        f"Best {BEST_N_DEFAULT} of {len(comp_order)}",
        value=False,
        help="Applies to points-based datasets.",
        key="an_best_n")
    n_eff = BEST_N_DEFAULT if use_best_n else None

# ── Build ranking data ────────────────────────────────────────────────────
meta    = DATASETS[dataset]
ranking = get_leaderboard_data(dataset, catches_f, anglers_f,
                                top_n=top_n, comp_order=comp_order,
                                best_n=n_eff)

title = f"{dataset} — {('All' if top_n is None else f'Top {top_n}')}"
if use_best_n and dataset in ("Overall Points per Angler", "Club Standings"):
    title += f" (best {BEST_N_DEFAULT} of {len(comp_order)})"

# ── Five chart-type tabs + table ─────────────────────────────────────────
tab_bar, tab_pie, tab_line, tab_per_ic, tab_table = st.tabs(
    ["📊  Bar chart", "🥧  Pie chart", "📈  Line chart",
     "🏆  Per IC", "📋  Table view"])


def _no_data() -> None:
    empty_state("No data to display with the current filters.", "📊")


def _caption(chart_data) -> None:
    n = len(chart_data["Category"].unique()) if not chart_data.empty else 0
    st.caption(f"Showing **{n}** {meta['category_label'].lower()}(s) after filters.")


# ── Bar chart ─────────────────────────────────────────────────────────────
with tab_bar:
    if ranking.empty:
        _no_data()
    else:
        chart_data = ranking[["Category", "Value"]].copy()
        fig = render_chart(chart_data, "bar", title=title,
                           value_label=meta["value_label"],
                           category_label=meta["category_label"])
        st.plotly_chart(fig, use_container_width=True)
        _caption(chart_data)

# ── Pie chart ─────────────────────────────────────────────────────────────
with tab_pie:
    if ranking.empty:
        _no_data()
    else:
        if dataset in ("Heaviest Edible", "Heaviest Non-Edible"):
            st.info(
                "Pie charts work best with grouped categories (clubs, divisions). "
                "For individual catches, the **Bar chart** tab is clearer.")
        chart_data = ranking[["Category", "Value"]].copy()
        fig = render_chart(chart_data, "pie", title=title,
                           value_label=meta["value_label"],
                           category_label=meta["category_label"])
        st.plotly_chart(fig, use_container_width=True)
        _caption(chart_data)

# ── Line chart ────────────────────────────────────────────────────────────
with tab_line:
    if ranking.empty:
        _no_data()
    else:
        if dataset in ("Heaviest Edible", "Heaviest Non-Edible"):
            st.info(
                "Line charts show progression across competitions. "
                "This dataset contains single catches — use **Bar** or **Pie** instead.")
        chart_data = get_trend_data(dataset, catches_f, anglers_f,
                                     top_n=top_n, comp_order=comp_order)
        # Relabel Comp -> "IC N (YYYY-MM-DD · Venue)" so the line x-axis carries dates+venues
        if not chart_data.empty:
            chart_data = chart_data.copy()
            chart_data["Comp"] = chart_data["Comp"].astype(str).map(_ic_label)
            # Preserve chronological order
            ordered_labels = [_ic_label(c) for c in comp_order]
            import pandas as _pd
            chart_data["Comp"] = _pd.Categorical(chart_data["Comp"],
                                                 categories=ordered_labels, ordered=True)
            chart_data = chart_data.sort_values(["Category", "Comp"])
        fig = render_chart(chart_data, "line", title=title,
                           value_label=meta["value_label"],
                           category_label=meta["category_label"])
        st.plotly_chart(fig, use_container_width=True)
        _caption(chart_data)

# ── Per IC breakdown ─────────────────────────────────────────────────────
with tab_per_ic:
    chart_data = get_trend_data(dataset, catches_f, anglers_f,
                                 top_n=top_n, comp_order=comp_order)
    if chart_data.empty:
        _no_data()
    else:
        # Pivot to wide: rows=Category, cols=Comp, values=Value
        import pandas as _pd
        wide = (chart_data.pivot_table(index="Category", columns="Comp",
                                         values="Value", aggfunc="sum",
                                         observed=False)
                .fillna(0))
        # Each column header = "IC N (date · venue)" so trends are dated
        wide = wide.reindex(columns=comp_order, fill_value=0)
        wide.columns = [_ic_label(str(c)) for c in wide.columns]
        wide["Total"] = wide.sum(axis=1)
        wide = wide.sort_values("Total", ascending=False)
        if top_n is not None:
            wide = wide.head(top_n)
        # Format numbers without matplotlib gradient (keeps deps minimal)
        is_weight = meta["value_label"].lower().startswith("weight")
        fmt = "{:,.2f}" if is_weight else "{:,.0f}"
        st.dataframe(wide.style.format(fmt), use_container_width=True)
        st.download_button(
            "⬇ Download per-IC CSV",
            wide.to_csv().encode(),
            file_name=f"{dataset.replace(' ', '_').lower()}_per_ic.csv",
            mime="text/csv", key="an_per_ic_dl")

# ── Table view ────────────────────────────────────────────────────────────
with tab_table:
    if ranking.empty:
        _no_data()
    else:
        section_label(f"{dataset} — {('all' if top_n is None else f'top {top_n}')}")
        st.dataframe(highlight_leader(ranking),
                     use_container_width=True, hide_index=True)
        if not ranking.empty:
            top_row = ranking.iloc[0]
            leader_banner(
                "🥇",
                str(top_row["Category"]),
                pts=f"{top_row['Value']:,.2f} {meta['value_label']}")
        st.download_button(
            "⬇ Download CSV",
            ranking.to_csv(index=False).encode(),
            file_name=f"{dataset.replace(' ', '_').lower()}_{('all' if top_n is None else f'top{top_n}')}.csv",
            mime="text/csv",
        )

# ── Species composition per IC ────────────────────────────────────────────
divider_label("Species composition per competition")
import pandas as _pd
import plotly.express as _px

cc = catches_f.copy()
cc["weight_kg"] = _pd.to_numeric(cc["weight_kg"], errors="coerce").fillna(0.0)
cc["valid"]    = cc["status"].fillna("").astype(str).str.lower().str.startswith("ok")
cc = cc[cc["valid"]].copy()
cc["comp_label"] = cc["comp_id"].astype(str).map(_ic_label)

with st.container(border=True):
    section_label("Choose metric")
    metric = st.radio(
        "Show composition by", ["Catch count", "Total weight (kg)"],
        horizontal=True, key="an_spec_metric")

    if cc.empty:
        empty_state("No catches match the current filters.", "🐟")
    else:
        # Aggregate species × IC
        if metric == "Catch count":
            agg = (cc.groupby(["comp_label", "canonical_species"]).size()
                   .reset_index(name="Value"))
            vfmt = "{:,.0f}"
        else:
            agg = (cc.groupby(["comp_label", "canonical_species"])["weight_kg"].sum()
                   .reset_index().rename(columns={"weight_kg": "Value"}))
            vfmt = "{:,.2f}"

        # Per-comp total, then % share per species
        comp_totals = agg.groupby("comp_label")["Value"].transform("sum")
        agg["% of IC"] = (agg["Value"] / comp_totals * 100).round(1)

        # Preserve IC order chronologically
        ordered_labels = [_ic_label(c) for c in comp_order]
        agg["comp_label"] = _pd.Categorical(agg["comp_label"],
                                            categories=ordered_labels, ordered=True)
        agg = agg.sort_values(["comp_label", "Value"], ascending=[True, False])

        # ── Stacked bar chart ─────────────────────────────────────────────
        fig = _px.bar(
            agg, x="comp_label", y="Value", color="canonical_species",
            title=f"Species composition per competition — {metric}",
            labels={"comp_label": "Competition", "Value": metric,
                    "canonical_species": "Species"},
            text="Value",
        )
        fig.update_layout(barmode="stack", xaxis_tickangle=-25, height=520)
        fig.update_traces(texttemplate=("%{y:.0f}" if metric == "Catch count" else "%{y:.1f}"),
                          textposition="inside", insidetextanchor="middle")
        st.plotly_chart(fig, use_container_width=True)

        # ── Pivot: species rows × IC columns, with % share per IC ────────
        section_label("Counts and percentages by IC")
        pivot_val = agg.pivot_table(index="canonical_species", columns="comp_label",
                                     values="Value", aggfunc="sum", observed=False).fillna(0)
        pivot_pct = agg.pivot_table(index="canonical_species", columns="comp_label",
                                     values="% of IC", aggfunc="sum", observed=False).fillna(0)
        # Combine into one frame with two-row column headers (Value, % of IC)
        pivot_combo = _pd.concat({"Value": pivot_val, "% of IC": pivot_pct}, axis=1)
        # Reorder so each IC has Value+% adjacent
        new_cols = []
        for ic in ordered_labels:
            if ("Value", ic) in pivot_combo.columns:
                new_cols += [("Value", ic), ("% of IC", ic)]
        pivot_combo = pivot_combo[new_cols]
        # Add a Total column
        pivot_combo[("Total", metric)] = pivot_val.sum(axis=1)
        pivot_combo = pivot_combo.sort_values(("Total", metric), ascending=False)
        # Format
        fmt_map = {col: (vfmt if col[0] in ("Value", "Total") else "{:,.1f}%")
                   for col in pivot_combo.columns}
        st.dataframe(pivot_combo.style.format(fmt_map), use_container_width=True)

        st.download_button(
            "⬇ Download species-composition CSV",
            pivot_combo.to_csv().encode(),
            file_name=f"species_composition_per_ic_{active}.csv",
            mime="text/csv", key="an_spec_dl")
