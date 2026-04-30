"""Analytics — interactive charts driven by sidebar controls.

Reuses get_leaderboard_data() / render_chart() from analytics.py — no
duplicate aggregation. Global Comp/Club/Division filters from app_lib are
applied first, then chart-specific controls (dataset / chart type / top N)
shape the visualisation.
"""
from __future__ import annotations

import streamlit as st

from analytics import (DATASETS, get_leaderboard_data, get_trend_data,
                       render_chart)
from app_lib import (apply_filters, highlight_leader, load_anglers,
                     load_catches_scored, render_global_filters,
                     render_season_sidebar)
from standings import BEST_N_DEFAULT

st.set_page_config(page_title="Analytics · WCSAA League",
                   page_icon="📊", layout="wide")
active = render_season_sidebar()
st.title(f"📊 Charts & Analytics — {active}")
st.caption("Interactive views of leaderboard data. Filters in the sidebar "
           "narrow the dataset; chart controls below pick what to visualise.")

catches = load_catches_scored()
anglers = load_anglers()

if catches.empty:
    st.info("No catches yet — record some on the Catches page first.")
    st.stop()

# ---- Global filters (Comp / Club / Division) ---------------------------
filters = render_global_filters(catches, anglers)
catches_f, anglers_f = apply_filters(catches, anglers, filters)
if catches_f.empty:
    st.warning("No catches match the current filters.")
    st.stop()

comp_order = sorted(catches_f["comp_id"].astype(str).unique().tolist())

# ---- Chart-specific controls (sidebar) ---------------------------------
with st.sidebar:
    st.markdown("### 📊 Charts & Analytics")
    dataset = st.selectbox("Dataset", list(DATASETS.keys()), key="an_dataset")
    chart_type = st.radio("Chart type", ["Bar", "Pie", "Line"],
                          horizontal=True, key="an_chart_type")
    top_n = st.select_slider("Top N", options=[5, 10, 15, 20, 30, 50],
                             value=10, key="an_top_n")
    use_best_n = st.toggle(f"Best {BEST_N_DEFAULT} of {len(comp_order)}",
                           value=False,
                           help="Applies to points-based datasets.",
                           key="an_best_n")
    n_eff = BEST_N_DEFAULT if use_best_n else None

# ---- Build the data ----------------------------------------------------
meta = DATASETS[dataset]
ranking = get_leaderboard_data(dataset, catches_f, anglers_f,
                                top_n=top_n, comp_order=comp_order,
                                best_n=n_eff)

# Pie charts are only meaningful for category aggregations, not "Top N catches"
# where each row is a unique fish — flag this to the user.
if chart_type == "Pie" and dataset in ("Heaviest Edible", "Heaviest Non-Edible"):
    st.info("Pie chart is most meaningful for grouped categories (clubs, "
            "divisions). For individual catches, prefer Bar.")

# Build chart data shape
if chart_type == "Line":
    chart_data = get_trend_data(dataset, catches_f, anglers_f,
                                 top_n=top_n, comp_order=comp_order)
else:
    chart_data = ranking[["Category", "Value"]].copy()

# ---- Render: tabs ------------------------------------------------------
tab_chart, tab_table = st.tabs(["📈 Chart View", "📋 Table View"])

title = f"{dataset} (Top {top_n})"
if use_best_n and dataset in ("Overall Points per Angler", "Club Standings"):
    title += f" — best {BEST_N_DEFAULT} of {len(comp_order)}"

with tab_chart:
    if ranking.empty:
        st.info("No data to chart with the current filters.")
    else:
        fig = render_chart(chart_data, chart_type, title=title,
                            value_label=meta["value_label"],
                            category_label=meta["category_label"])
        st.plotly_chart(fig, use_container_width=True)
        n_show = len(chart_data["Category"].unique()) if not chart_data.empty \
            else 0
        st.caption(f"Showing **{n_show}** {meta['category_label'].lower()}(s) "
                   f"after filters.")

with tab_table:
    if ranking.empty:
        st.info("No data with the current filters.")
    else:
        st.dataframe(highlight_leader(ranking),
                     use_container_width=True, hide_index=True)
        st.download_button(
            "⬇ Download CSV",
            ranking.to_csv(index=False).encode(),
            file_name=f"{dataset.replace(' ', '_').lower()}_top{top_n}.csv",
            mime="text/csv",
        )
