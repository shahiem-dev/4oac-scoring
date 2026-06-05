# WCSAA Grand Prix Scoring — Proposal Analysis & Implementation Plan

**Audience:** WCSAA committee / stakeholders + dev.
**Source:** `WCSAA Point system discussion document 1 June 2026.pdf`
**Premise:** Enhance the **existing** staging platform — do **not** rebuild. The Grand Prix (GP) model is added *alongside* the current weight-points system as a parallel, toggleable view.
**Status:** Analysis + validated simulation on real 2025-26 data. Build gated on the open decisions in §11.

---

## 1. Executive Summary

The proposal converts each angler's per-competition **weight points** into **Grand Prix points** capped at **50 per IC**, by expressing each angler's score as a percentage of the top score in that IC. It optionally adds **+1 "fish point" per qualifying fish** to reward work-rate.

**Why it matters:** the current cumulative-weight system rewards "bigger is better" — one giant fish or two bonus ICs can carry an angler who then coasts or skips events. That trains the wrong habits for Nationals (where width of skill and consistency win). GP puts a "hand-brake" on single huge catches and **rewards scoring in every IC**.

**Key finding — it fits the existing platform with surprisingly little new infrastructure.** The current engine already builds a per-angler × per-competition matrix (`standings.per_entity_per_comp`) and already supports "best-N-of-M, drop-worst" (`standings.apply_best_n`). GP is a **thin transform** on top of that matrix. No schema migration is required for the core feature.

**We validated the model on the live 2025-26 data (218 anglers, 8 ICs)** and it reproduces the proposal's own simulation almost exactly (see §3). Recommendation: **proceed**, as an additive "Grand Prix (Trial)" view, phased. Estimated effort **Medium** (~3–5 dev days for Phases 1–2).

---

## 2. Proposal Analysis

### 2.1 Current system (already live)
| Rule | Value |
|---|---|
| Non-edibles | 1 pt/kg (1 kg minimum) |
| Edibles | 4 pts/kg (0.5 kg minimum) |
| Sight fish (barbel/gurnard/catfish) | 1 pt flat |
| League winner | cumulative weight points over 8 ICs |
| Selection aid | position-per-IC "rank points", **drop worst (7 of 8 count)** |

### 2.2 Proposed Grand Prix model (Version A — points-based)

Keeps the same weight-point building blocks, then **per IC**:

```
Achievement%(angler, IC) = weight_points(angler, IC) / max_weight_points(IC)
GP_points(angler, IC)    = Achievement% × 50
Season GP total          = Σ GP_points across ICs   (drop-worst optional — see §11)
```

Worked example from the proposal (verified against the formula):

| | Weight pts | Achievement | GP pts |
|---|---|---|---|
| IC1 top (110 wp) | 110 | 100% | **50.0** |
| 90 wp | 90 | 81.8% | 40.9 |
| IC3 bonus-fish top (200 wp) | 200 | 100% | **50.0** ← capped to same 50 as IC1 top |

**Effects:** the impact of one massive IC is capped (200 wp → 50, same as a 110 wp top); the differentiation *between* anglers is retained (it is proportional, not pure rank); consistency is rewarded; "blobbing" (zero ICs) is punished because each zero forfeits up to 50 points.

### 2.3 Optional "1 point per fish" (work-rate) layer
- **+1 point per fish** that meets the minimum weight (0.5 kg ed / 1 kg non-ed).
- **Excludes sight fish.**
- Added on top of the GP base (the proposal's example: "45 + 20 fish = 65" — additive after conversion; **needs confirmation, see §11**).
- Rewards targeting small–medium fish and raw work-rate — the skills WP lacks at Nationals. (Boland's "release points" is the precedent.)

### 2.4 Gaps & ambiguities (must be resolved before build — see §11)
1. **Drop-worst for GP league total?** Current selection uses 7/8. Does the GP *league standing* sum all 8 or best 7?
2. **Fish points timing** — added after GP conversion (uncapped) or to weight points before conversion (stays ≤50)?
3. **Pool for "max in IC"** — overall field, or per division (Senior/Master/GM/Junior/Lady), or per league?
4. **Scope** — individual only, or also team/club standings and divisional standings?
5. **Tie-breakers** — equal GP totals broken by weight pts? fish count? head-to-head?
6. **Version A vs B** — proposal details Version A (points). Confirm A is the trial model.
7. **Replace vs parallel** — confirmed assumption: **parallel/trial**, weight points remain the official league result during the trial.

---

## 3. Real-Data Simulation (proof on the live 2025-26 season)

Computed by `scripts/gp_simulation.py` over the **actual ingested data** (218 anglers, IC 1–8), overall pool, GP all-8. This is not synthetic — it is the real season restated.

**Top of the table — weight rank → GP rank:**

| Wgt Rank | GP Rank | Move | Angler | Club | Weight pts | GP pts | Fish | Blobs |
|---:|---:|:--:|---|---|---:|---:|---:|---:|
| 1 | 1 | = | Donald Van Blommenstein | TYGERBERG | 710.2 | 225.5 | 38 | 2 |
| 2 | 2 | = | CT Bailey | TWO OCEANS | 633.2 | 149.5 | 81 | 0 |
| 3 | 5 | ▼2 | Mike Bailey | TWO OCEANS | 544.5 | 103.5 | 20 | 2 |
| 5 | 12 | ▼7 | Joshua Cochius | TWO OCEANS | 417.8 | 86.3 | 29 | 3 |
| 7 | 3 | ▲4 | Jason Selby | TWO OCEANS | 344.2 | 147.2 | 63 | 1 |
| 15 | 10 | ▲5 | Shahiem Adams | FOUR OCEANS | 268.9 | 93.2 | 39 | 2 |
| 18 | 43 | ▼25 | David Kotzee | TYGERBERG | 236.7 | 50.1 | 26 | 2 |
| 21 | 49 | ▼28 | Azmie Osman | FOUR OCEANS | 222.3 | 47.7 | 27 | 3 |

**This mirrors the proposal's own graph almost exactly:**
- "No change in positions #1 & #2" → confirmed (Van Blommenstein, CT Bailey hold).
- "Angler #7 moves to #3 due to consistency" → **Jason Selby #7 → #3** (1 blob, 63 fish, scored everywhere).
- "Anglers #19 & #22 drop to #43 & #49 — big fish diminished + blobs" → **Kotzee #18→#43, Osman #21→#49** — the same magnitude of fall.

**Biggest fallers** are single-big-fish or frequent-blob anglers (Marlin Small #84→#135, 5 blobs / fished only 3). **Biggest risers** are consistent mid-pack anglers. The model behaves exactly as intended on real data.

Full per-angler output: `raw/notes/wcsaa-gp-sim/gp_full.csv` (weight/GP-all8/GP-best7/fish/GP+fish columns and all four rank columns).

---

## 4. Existing Platform Review — Reuse Map

| Layer | Asset | GP reuse |
|---|---|---|
| **Engine** | `standings.per_entity_per_comp()` builds entity×comp weight-point matrix | **Reuse directly** — GP is column-normalise × 50 of this matrix |
| **Engine** | `standings.apply_best_n()` drop-worst | **Reuse** for GP drop-worst (decision §11.1) |
| **Engine** | `app_lib.points_for()` weight points | **Reuse** as GP input |
| **Data** | `catches_scored` (weight_kg, edible, canonical_species, comp_id, wp_no) | **Reuse** — fish points = count of qualifying rows; no new columns needed |
| **Page** | `4_Standings.py` tabs (By Club / Individuals / By Division / Drilldown) | **Enhance** — add GP columns / a GP sub-tab |
| **Page** | `9_Analytics.py` datasets + IC/venue filters | **Enhance** — add GP datasets + weight-vs-GP comparison chart |
| **Page** | `5_Reports.py` season summaries + XLSX | **Enhance** — add GP standings sheet |
| **Page** | `Home.py` Club Standings / Top-10 | **Enhance** — optional GP toggle |
| **Page** | `3_Competitions.py` per-comp | **Enhance** — show per-IC GP conversion |
| **New** | "Grand Prix (Trial)" page + "Angler Profile" page + "Selection Simulator" | **New** components |
| **Config** | season/theme settings | **Extend** — `scoring_mode` toggle per season |

**Net:** ~80% reuse. New work is one engine module (`grandprix.py`), UI surfacing, and two new pages.

---

## 5. Page-by-Page Enhancements (Before → After)

### A. Rankings / Standings page
- **Before:** Individuals tab ranks by cumulative weight points.
- **After:** add a **"Grand Prix (Trial)"** sub-tab and optional columns: `GP pts`, `GP rank`, `Δ vs weight rank` (▲/▼ badge reusing the existing `status_pill`/`leader_banner` styling), `Fish pts`, `ICs scored / blobbed`. Toggle: *Weight | GP | GP + Fish*; toggle: *All 8 | Best 7*.

### B. Competition Results page (`3_Competitions`)
- **Before:** per-IC weight totals.
- **After:** per-IC table gains `Achievement %` and `GP (×50)` columns so an angler sees "you scored 78% of the IC top = 39 GP pts". Shows the "hand-brake" in action on bonus-fish days.

### C. Angler Profile page (NEW)
- Historical results across IC 1–8 (weight, GP, fish per IC — sparkline reusing Analytics line chart).
- Season GP earned + GP rank + **ranking movement** vs weight rank.
- **Qualification status** badge against the selection cut-off (§D).
- Consistency metric: ICs scored / blobbed.

### D. Provincial Selection page (NEW — selectors only)
- **Before:** manual, weight + position rank-points, drop-worst 7/8.
- **After:** **Selection Simulator** — pick model (Weight rank-points / GP / GP+Fish), pick division, set cut-off (top-N or threshold); table shows who qualifies, who's on the bubble, and **what changes vs the current method**. "What-if" sliders for best-7 vs all-8.

### E. Reporting Dashboard (`9_Analytics` + `5_Reports`)
- New charts: **weight-rank vs GP-rank butterfly** (reproduces the proposal graph from live data), per-IC GP heatmap, consistency scatter (ICs scored vs GP), fish-points leaderboard.
- New metrics: average GP/IC, blob count, achievement-% distribution.
- New XLSX sheet: "Grand Prix Standings" + "Selection Simulation".

---

## 6. Side-by-Side: Existing vs Grand Prix

| Dimension | Existing (Weight) | Grand Prix |
|---|---|---|
| Ranking driver | Cumulative kg-points | % of IC-top, capped 50/IC |
| Big single catch | Can dominate season | Capped — max 50 that IC |
| Consistency | Not required | Strongly rewarded |
| Blobbing / skipping ICs | Survivable if 1–2 big ICs | Heavily punished |
| Differentiation | Full (raw kg gap) | Retained, proportional |
| Selection alignment | Indirect (separate rank-points) | Bridges weight ↔ rank-points |
| Participation incentive | Weak | Strong ("catch what's in front of you") |
| Skill-width for Nationals | Poor | Improved (esp. with fish points) |
| Admin | Existing | Same inputs; one extra computed view |
| Angler comprehension | High ("they get it") | Medium — needs the "÷top ×50" explainer |

---

## 7. Technical Assessment (per enhancement)

| Enhancement | User benefit | Data fields | DB impact | UI impact | Reporting | Complexity |
|---|---|---|---|---|---|---|
| GP engine `grandprix.py` | Core model | existing matrix | none | none | feeds all | **Low** |
| Standings GP sub-tab/cols | See GP rank + movement | computed | none | medium | — | **Low–Med** |
| Competition GP columns | See achievement% per IC | computed | none | low | — | **Low** |
| Fish-points layer | Work-rate reward | count of qualifying catches | none (computed) | low | — | **Low** |
| Analytics GP charts | Stakeholder proof | computed | none | medium | charts | **Medium** |
| Reports GP sheet | Offline/print | computed | none | low | XLSX | **Low** |
| Angler Profile page (new) | Per-angler story | existing | none | medium | — | **Medium** |
| Selection Simulator (new) | Selector decisions | existing + cut-off config | optional `selection_config` | high | XLSX | **Medium–High** |
| `scoring_mode` season toggle | Trial vs official switch | new config field | small (1 col / config row) | low | — | **Low** |

---

## 8. Data Model Recommendations

- **Core GP: no schema change.** Everything derives from `catches_scored` + the existing matrix builder.
- **Optional (Phase 2):** `scoring_config` singleton/per-season row — `{season_id, mode: weight|gp|gp_fish, gp_max: 50, drop_worst: bool, pool: overall|division}`. Lets the committee flip the trial without code edits.
- **Optional (Phase 3, selection):** `selection_config` — `{season_id, division, method, cutoff_type, cutoff_value}` to persist selector scenarios.
- **Performance:** at ~5k catches the on-the-fly compute is instant; no materialisation needed. Revisit only if multi-season analytics get heavy.

---

## 9. Workflow

```
Capture catches (unchanged)
        ↓
catches_scored  (weight_kg, edible, species)  ── unchanged engine
        ↓
per_entity_per_comp  →  weight matrix [angler × IC]        (EXISTING)
        ↓ grandprix.to_gp(matrix, gp_max=50, pool, drop_worst)
GP matrix [angler × IC]  + fish-point matrix (count per IC)
        ↓ aggregate (+ optional best-N)
Season GP / GP+Fish totals  →  Standings · Profile · Selector · Reports · Analytics
```

The committee flips `scoring_mode`; nothing in the capture or scoring-of-catches path changes.

---

## 10. Final Recommendation

**Can it be accommodated in the existing staging site? Yes — comfortably, as an additive trial view.** It reuses the matrix engine and drop-worst logic already in production; the core is a Low-complexity transform.

**Level of effort:** Phase 1–2 ≈ 3–5 dev days. Full (incl. Selection Simulator + config) ≈ 8–10 days.

**Risks:**
- *Scoring ambiguities (§11)* — must be locked before build or the numbers will be re-litigated. **Mitigation:** decisions table below.
- *Angler comprehension* — needs a clear in-app "how GP is calculated" explainer.
- *Shared staging/prod DB* — all work is read-only computation; no data writes. Restore point `restore/pre-grandprix-2026-06-05` + full backup taken.
- *Trial credibility* — show GP **beside** weight (never replace) until the committee signs off.

**Advantages:** rewards consistency & participation; caps single-fish distortion; bridges to the selectors' rank-points; builds Nationals-relevant skill width; near-zero data risk; fast to prototype on real data.

### Suggested phased rollout
| Phase | Scope | Effort | Gate |
|---|---|---|---|
| **0 — Decisions** | Lock §11 answers | — | committee |
| **1 — Engine + read-only proof** | `grandprix.py`; "Grand Prix (Trial)" tab on Standings; weight-vs-GP chart on Analytics; live 2025-26 restatement | Low–Med | internal review |
| **2 — Fish points + Reports** | fish-point layer; GP XLSX sheet; Competition per-IC GP columns | Low | committee demo |
| **3 — Profiles + Selection Simulator** | Angler Profile page; Selection Simulator; `scoring_config`/`selection_config` | Med–High | selectors |
| **4 — Adopt / iterate** | Optionally make GP the headline for a future season after a full trial season | — | AGM |

All Phase 1–3 work lands on **staging** behind the orange banner; promotion to `main` (production) only on committee sign-off, with a tagged restore point per promotion.

---

## 11. Open Decisions (needed before Phase 1 build)

| # | Decision | Options | Default if unanswered |
|---|---|---|---|
| 1 | Drop-worst for GP league total | All 8 / Best 7 of 8 | Show **both** (toggle) |
| 2 | Fish points timing | After GP (uncapped) / before conversion (≤50) | **After GP** (matches worked example) |
| 3 | "Max in IC" pool | Overall / per division / per league | **Overall** (matches proposal graph) |
| 4 | Scope | Individuals only / + teams / + divisions | **Individuals only** for trial |
| 5 | Tie-breaker | Weight pts / fish count / head-to-head | **Weight pts** |
| 6 | Model version | A (points) / B (rank) | **A** |
| 7 | Trial vs replace | Parallel trial / replace weight | **Parallel trial** |

---

*Generated 2026-06-05. Simulation: `scripts/gp_simulation.py`. Restore point: `restore/pre-grandprix-2026-06-05`.*
