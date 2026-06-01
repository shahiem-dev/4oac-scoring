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

# Venue filter (join comps → catches via comp_id)
comps_df = load_comps()
if not comps_df.empty:
    venues = sorted(comps_df["venue"].dropna().unique().tolist())
    with st.sidebar:
        st.markdown("### 📍 Venue filter")
        selected_venues = st.multiselect(
            "Venue", venues, default=[], key="an_venue",
            help="Leave empty to include all venues.")
    if selected_venues:
        venue_comp_ids = (comps_df[comps_df["venue"].isin(selected_venues)]
                          ["comp_id"].astype(str).tolist())
        catches_f = catches_f[catches_f["comp_id"].astype(str).isin(venue_comp_ids)]
        if catches_f.empty:
            st.warning(f"No catches found at venue(s): {', '.join(selected_venues)}.")
            st.stop()

comp_order = sorted(catches_f["comp_id"].astype(str).unique().tolist())

# ── Dataset + Top-N controls (sidebar) ───────────────────────────────────
with st.sidebar:
    st.markdown("### 📊 Chart controls")
    dataset = st.selectbox("Dataset", list(DATASETS.keys()), key="an_dataset")
    top_n   = st.select_slider("Top N", options=[5, 10, 15, 20, 30, 50],
                                value=10, key="an_top_n")
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

title = f"{dataset} — Top {top_n}"
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
        wide.columns = [f"IC {c}" for c in wide.columns]
        wide["Total"] = wide.sum(axis=1)
        wide = wide.sort_values("Total", ascending=False).head(top_n)
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
        section_label(f"{dataset} — top {top_n}")
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
            file_name=f"{dataset.replace(' ', '_').lower()}_top{top_n}.csv",
            mime="text/csv",
        )
