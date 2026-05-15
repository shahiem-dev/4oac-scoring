"""Live standings — clubs, individuals, per-league, club drilldown."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from auth import require_login
require_login()

from app_lib import (DIVISIONS, apply_filters, load_anglers,
                     load_catches_scored, load_comps, render_global_filters,
                     render_season_sidebar, resolve_sub_team)
from standings import (BEST_N_DEFAULT, apply_best_n, per_entity_per_comp,
                       style_dropped)
from ui import divider_label, kpi_row, leader_banner, page_header, section_label

st.set_page_config(page_title="Standings · WCSAA League", page_icon="🏆", layout="wide")
active = render_season_sidebar()
page_header("Live Standings", "Club & individual rankings updated in real time",
            "🏆", active)

catches = load_catches_scored()
anglers = load_anglers()
comps   = load_comps()

if catches.empty:
    st.info("No catches yet — standings will appear once catches are recorded.")
    st.stop()

filters = render_global_filters(catches, anglers)
catches, anglers = apply_filters(catches, anglers, filters)
if catches.empty:
    st.warning("No catches match the current filters.")
    st.stop()

# ── Enrich ────────────────────────────────────────────────────────────────
cc = resolve_sub_team(catches, anglers).merge(
    anglers.drop(columns=["sub_team"], errors="ignore"), on="wp_no", how="left")
cc["club"]     = cc["club"].fillna("UNKNOWN").replace("", "UNKNOWN")
cc["sub_team"] = cc["sub_team"].fillna("").astype(str).str.upper().str.strip()
cc["Angler"]   = (cc["first_name"].fillna("") + " " + cc["surname"].fillna("")).str.strip()
cc.loc[cc["Angler"] == "", "Angler"] = "(unknown)"
comp_order = sorted(catches["comp_id"].unique().tolist())
SUB_TEAMS  = list("ABCDEFGHI")

# ── Season KPIs ───────────────────────────────────────────────────────────
kpi_row([
    {"icon": "📅", "label": "Competitions",   "value": len(comp_order)},
    {"icon": "👥", "label": "Anglers active", "value": cc["wp_no"].nunique()},
    {"icon": "🐟", "label": "Valid catches",
     "value": int(catches["status"].str.startswith("ok").sum())},
    {"icon": "⭐", "label": "Total points",
     "value": f"{catches['points'].sum():,.0f}"},
])

# ── Scoring mode toggle ───────────────────────────────────────────────────
st.sidebar.markdown("### Scoring mode")
use_best_n = st.sidebar.toggle(
    f"Best {BEST_N_DEFAULT} of {len(comp_order)}",
    value=False,
    help=f"Drop each entity's lowest scores so only the best "
         f"{BEST_N_DEFAULT} comps count. Dropped cells are struck-through.",
)
mode_label = f"Best {BEST_N_DEFAULT}" if use_best_n else "All comps"
st.caption(f"Mode: **{mode_label}** · {len(comp_order)} competition(s)")

# ── Tabs ─────────────────────────────────────────────────────────────────
tab_club, tab_ind, tab_league, tab_drill = st.tabs(
    ["🏛  By Club", "👤  Individuals", "🎖  By Division", "🔍  Club Drilldown"])

# ---- By Club ------------------------------------------------------------
with tab_club:
    section_label("Sub-team breakdown (A–I + A+B)")
    sub = cc.pivot_table(index="club", columns="sub_team",
                         values="points", aggfunc="sum")
    sub = sub.reindex(columns=SUB_TEAMS)
    out = pd.DataFrame(index=sub.index)
    out["PNTS A"] = sub["A"]; out["PNTS B"] = sub["B"]
    ab = sub["A"].fillna(0) + sub["B"].fillna(0)
    ab[sub["A"].isna() & sub["B"].isna()] = pd.NA
    out["PNTS A+B"] = ab
    for t in SUB_TEAMS[2:]:
        out[f"PNTS {t}"] = sub[t]
    out = out.sort_values("PNTS A+B", ascending=False,
                          na_position="last").reset_index()
    out.insert(0, "Pos.", range(1, len(out) + 1))
    out = out.rename(columns={"club": "CLUB"})
    st.dataframe(out, use_container_width=True, hide_index=True)
    st.download_button("⬇ CSV", out.to_csv(index=False).encode(),
                       "club_subteam_standings.csv", "text/csv")

    divider_label("Per-competition totals")
    matrix = per_entity_per_comp(cc, "club", comp_order)
    _, dropped, total = apply_best_n(
        matrix, n=BEST_N_DEFAULT if use_best_n else 10**6)
    pivot = matrix.copy()
    pivot["Total"] = total
    pivot = pivot.sort_values("Total", ascending=False).reset_index()
    pivot.insert(0, "Pos.", range(1, len(pivot) + 1))
    pivot = pivot.rename(columns={"club": "Club"})
    if use_best_n and not dropped.empty:
        dropped_aligned = dropped.reindex(pivot["Club"]).reset_index(drop=True)
        st.dataframe(style_dropped(pivot, dropped_aligned, comp_order),
                     use_container_width=True, hide_index=True)
    else:
        st.dataframe(pivot, use_container_width=True, hide_index=True)
    if not pivot.empty:
        w = pivot.iloc[0]
        leader_banner("🥇", w["Club"], pts=f"{w['Total']:,.2f} pts")
    st.download_button("⬇ CSV", pivot.to_csv(index=False).encode(),
                       "club_per_comp_standings.csv", "text/csv")

# ---- Individuals --------------------------------------------------------
with tab_ind:
    matrix = per_entity_per_comp(cc, "wp_no", comp_order)
    _, dropped, total = apply_best_n(
        matrix, n=BEST_N_DEFAULT if use_best_n else 10**6)
    pivot = matrix.copy()
    pivot["Total"] = total
    meta = (cc.drop_duplicates("wp_no")[["wp_no", "Angler", "club", "league_code"]]
              .set_index("wp_no"))
    pivot = (pivot.join(meta).sort_values("Total", ascending=False)
             .reset_index())
    pivot.insert(0, "Rank", range(1, len(pivot) + 1))
    pivot = pivot.rename(columns={"wp_no": "WP No", "club": "Club",
                                   "league_code": "Lg"})
    cols = ["Rank", "WP No", "Angler", "Club", "Lg"] + comp_order + ["Total"]
    pivot = pivot[cols]
    if use_best_n and not dropped.empty:
        dropped_aligned = dropped.reindex(pivot["WP No"]).reset_index(drop=True)
        st.dataframe(style_dropped(pivot, dropped_aligned, comp_order),
                     use_container_width=True, hide_index=True)
    else:
        st.dataframe(pivot, use_container_width=True, hide_index=True)
    if not pivot.empty:
        w = pivot.iloc[0]
        leader_banner("🥇", w["Angler"], detail=w["Club"],
                      pts=f"{w['Total']:,.2f} pts")
    st.download_button("⬇ CSV", pivot.to_csv(index=False).encode(),
                       "individual_standings.csv", "text/csv")

# ---- By Division --------------------------------------------------------
with tab_league:
    leagues = sorted([x for x in cc["league_code"].dropna().unique() if x != ""])
    if not leagues:
        st.info("No divisions set on anglers — set them on the **Clubs** page.")
    for lg in leagues:
        section_label(f"{lg} — {DIVISIONS.get(lg.upper(), '')}")
        sub = cc[cc["league_code"] == lg]
        matrix = per_entity_per_comp(sub, "wp_no", comp_order)
        _, dropped, total = apply_best_n(
            matrix, n=BEST_N_DEFAULT if use_best_n else 10**6)
        p = matrix.copy(); p["Total"] = total
        meta = (sub.drop_duplicates("wp_no")[["wp_no", "Angler", "club"]]
                .set_index("wp_no"))
        p = (p.join(meta).sort_values("Total", ascending=False)
             .reset_index())
        p.insert(0, "Rank", range(1, len(p) + 1))
        p = p.rename(columns={"wp_no": "WP No", "club": "Club"})
        cols = ["Rank", "WP No", "Angler", "Club"] + comp_order + ["Total"]
        p = p[cols]
        if use_best_n and not dropped.empty:
            d = dropped.reindex(p["WP No"]).reset_index(drop=True)
            st.dataframe(style_dropped(p, d, comp_order),
                         use_container_width=True, hide_index=True)
        else:
            st.dataframe(p, use_container_width=True, hide_index=True)
        if not p.empty:
            w = p.iloc[0]
            leader_banner("🥇", w["Angler"], detail=w["Club"],
                          pts=f"{w['Total']:,.2f} pts")

# ---- Club Drilldown -----------------------------------------------------
with tab_drill:
    clubs = sorted(cc["club"].unique().tolist())
    club  = st.selectbox("Select a club", clubs)
    sub   = cc[cc["club"] == club]
    matrix = per_entity_per_comp(sub, "wp_no", comp_order)
    _, dropped, total = apply_best_n(
        matrix, n=BEST_N_DEFAULT if use_best_n else 10**6)
    p = matrix.copy(); p["Total"] = total
    meta = (sub.drop_duplicates("wp_no")[["wp_no", "Angler", "league_code"]]
            .set_index("wp_no"))
    p = (p.join(meta).sort_values("Total", ascending=False)
         .reset_index())
    p.insert(0, "Rank", range(1, len(p) + 1))
    p = p.rename(columns={"wp_no": "WP No", "league_code": "Lg"})
    cols = ["Rank", "WP No", "Angler", "Lg"] + comp_order + ["Total"]
    p = p[cols]

    section_label(f"{club} — members")
    if use_best_n and not dropped.empty:
        d = dropped.reindex(p["WP No"]).reset_index(drop=True)
        st.dataframe(style_dropped(p, d, comp_order),
                     use_container_width=True, hide_index=True)
    else:
        st.dataframe(p, use_container_width=True, hide_index=True)
    if not p.empty:
        w = p.iloc[0]
        leader_banner("🥇", w["Angler"], detail=f"Lg {w['Lg']}",
                      pts=f"{w['Total']:,.2f} pts")

    divider_label(f"{club} — catch detail")
    detail = (sub[["comp_id", "wp_no", "Angler", "species_raw", "length_cm",
                   "weight_kg", "edible", "points", "status"]]
              .rename(columns={"comp_id": "Comp", "wp_no": "WP No",
                                "species_raw": "Species", "length_cm": "Length",
                                "weight_kg": "Weight", "edible": "Ed",
                                "points": "Pts", "status": "Status"}))
    st.dataframe(detail.sort_values(["Comp", "WP No"]),
                 use_container_width=True, hide_index=True)
