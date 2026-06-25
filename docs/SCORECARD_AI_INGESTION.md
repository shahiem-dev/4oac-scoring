# WCSAA Scorecard AI Ingestion — Architecture & Implementation Plan

**Status:** design locked → **zero-cost PoC** is the active path (Section 14, 2026-06-25). Template registry built (`config/scorecard_templates.json`). All §13 decisions resolved: capture = species + length; fish-sex M/F; **no WhatsApp**; **no paid budget** (Claude Code batch extraction, $0). Next concrete step: golden set (needs real card images). No pipeline code yet.
**Author:** Claude (with Shahiem), 2026-06-12 (updated 2026-06-25)
**Inputs:** 3 sample scorecard photos (Ver Oct 2023, Ver Oct 2024, Ver Sept 2025) — see
`raw/notes/wcsaa-scorecard-samples-2026-06-12.md` in the second brain.

---

## 1. Executive summary

A **Template-Aware Scorecard Recognition Engine** that turns a WhatsApp photo of a
handwritten WCSAA Tournament Scorecard into validated, structured catch records with
an explicit confidence score per field and a human CONFIRM step before anything is
committed to the database.

**Core recommendation:** use **Claude vision (Sonnet 4.6) as the extraction engine**,
driven by a version-keyed **template registry (JSON)**, followed by a **deterministic
validation suite** that computes real confidence from cross-checks — not from the
model's self-assessment. Classical zone-based OCR (Textract / Azure DI / Tesseract)
is the wrong tool for this corpus: the limiting factor is messy field handwriting on
creased, stained, hand-held cards, which document-AI services handle poorly without
expensive per-version custom training.

| Target | Plan |
|---|---|
| 98%+ field accuracy | Vision LLM + redundant-field cross-validation (the card itself is the checksum) |
| <5% manual review | Confidence from deterministic validators; only failed checks go to review |
| 10,000+ cards/year | Stateless pipeline on Supabase Edge Functions; ~$0.02–0.05/card on Sonnet |

---

## 2. What the samples actually tell us

Findings from the three real cards — these drive the design:

1. **Three template versions exist already** (Oct 2023, Oct 2024, Sept 2025) with
   real drift: the witness column was renamed (*WCSAA No* → *WP No*), the Sept 2025
   card adds a **U/13 ASSISTED** division, and the version string sits bottom-right
   ("Ver. Sept 2025"). Version-aware templates are justified, not speculative.
2. **The card has a built-in checksum.** Length is written twice — numeric (`134`)
   and in words (`ONE THREE FOUR`). Agreement between the two is the single
   strongest accuracy signal available and costs nothing.
3. **Species are written as colloquial shorthand** ("COW", "SANDY", "EAGLE RAY"),
   often by a tired angler on a beach. A fixed species lexicon + fuzzy matching is
   mandatory; free-text species must never pass through.
4. **The MALE/FEMALE column is the fish's sex, not the witness's.** The existing
   season data confirms it — species strings like `Guitarfish (Bluntnose)(M)` carry
   the fish's sex, which matters for shark/ray records. The spec's "Witness Gender"
   label is a misreading of the form; the schema below models it as `fish_sex`.
   (Flagging rather than silently following the spec.)
5. **Times are chaos**: `8.40`, `9 am`, `9:20`, `10h40`, `1:30PM`, `358`, `3:29`.
   Normalization must be deterministic code, not the LLM.
6. **Capture conditions are hostile**: rotation (sample 1 is 90° off), fingers,
   creases, sticky-tape repairs, smudged ink, vehicle-interior shadows. Preprocessing
   must be tolerant; the extractor must work on imperfect images because most images
   will be imperfect.
7. **Witness WP numbers repeat down the card** (same witness signs several rows) and
   are validatable against the member roster — a second free cross-check.

---

## 3. Technology evaluation

| Criterion | Claude Vision (Sonnet 4.6) | GPT-4.1 Vision | Azure Document Intelligence | AWS Textract |
|---|---|---|---|---|
| Messy handwriting | **Strong** — reads cursive/smudged in context | Strong | Moderate — needs custom neural model per layout | Weak-moderate on handwriting |
| Table structure on creased, skewed photos | **Strong** (semantic, not geometric) | Strong | Good only on flat scans | Good only on flat scans |
| Checkbox/circle mark detection (club, division) | **Strong** — understands "2/Oc is circled" | Strong | Selection marks supported but brittle on circles drawn around text | Limited |
| Template version awareness | Prompt-level — zero training | Prompt-level | Custom model **per version** ($, retraining on drift) | Custom queries per version |
| Semantic normalization in-pass (species, dates) | **Yes** — one call does extraction + mapping | Yes | No — separate post-processing layer needed | No |
| Structured/validated JSON output | **Native (structured outputs)** | Native | JSON but layout-shaped, not domain-shaped | JSON key-value, not domain-shaped |
| Cost per card (est.) | $0.02–0.05 | similar | $0.01–0.05 (custom model) + post-processing compute | $0.01–0.07 + post-processing |
| Ops fit (existing stack) | **Already integrated** — Anthropic key, Supabase Edge Functions, this codebase | New vendor | New cloud + training pipeline | New cloud + training pipeline |

**Recommendation: Claude Vision, single-pass extraction.** The decisive arguments:

- The hard part of this corpus is *understanding bad handwriting in context*
  ("SANDY" in a species column on a fishing scorecard), which is exactly what a
  vision LLM does and exactly what geometric OCR doesn't.
- Document-AI services would need a trained custom model **per template version**,
  re-trained on every form revision — WCSAA has already revised the form three times
  in three years.
- One Claude call replaces the entire OCR → cleanup → fuzzy-map → normalize chain,
  and the deterministic validators (Section 6) then provide the accuracy guarantees
  the LLM alone cannot.
- "Zone-based OCR" survives in the design as **zone-based prompting + optional
  zone cropping** (Section 5), keeping the template-aware requirement without
  betting accuracy on pixel coordinates measured from bent paper.

Escalation path: run **Haiku 4.5 first** (~$0.005–0.01/card); if any validator fails
or confidence is low, re-run on **Sonnet 4.6**; only then route to a human. At
expected WCSAA volume this keeps annual cost in the tens of dollars (Section 10).

---

## 4. Pipeline architecture

```
WhatsApp photo                    Streamlit upload (admin/bulk)
      │                                   │
      ▼                                   ▼
┌──────────────────────────────────────────────────┐
│ 1. INTAKE  (Edge Function: scorecard-ingest)     │
│    store original → Supabase Storage             │
│    create scorecard_submissions row (status=new) │
└──────────────┬───────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────┐
│ 2. PREPROCESS (server-side, deterministic)       │
│    EXIF orient · coarse rotation fix · resize    │
│    to ≤2576px long edge · contrast normalize     │
│    keep: original + corrected image              │
└──────────────┬───────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────┐
│ 3. TEMPLATE ID + EXTRACTION (one Claude call)    │
│    model reads "Ver ..." → selects template      │
│    registry entry → version-specific field list  │
│    & zone prompts → strict JSON schema output    │
└──────────────┬───────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────┐
│ 4. VALIDATION SUITE (pure code, no AI)           │
│    length-cm ↔ length-words cross-check          │
│    species fuzzy-match to lexicon                │
│    club/division enum check                      │
│    witness WP lookup vs anglers table            │
│    angler WP lookup + name agreement             │
│    time normalization → HH:mm, monotonic check   │
│    date vs competition calendar                  │
└──────────────┬───────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────┐
│ 5. CONFIDENCE + ROUTING                          │
│    all checks pass → auto-accept candidate       │
│    any check fails → review_required fields      │
└──────────────┬───────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────┐
│ 6. HUMAN LOOP                                    │
│    WhatsApp: summary → CONFIRM / CORRECT         │
│    Streamlit: Review queue page (side-by-side    │
│    image + editable extracted fields)            │
└──────────────┬───────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────┐
│ 7. COMMIT                                        │
│    staging rows → catches_raw / catches_scored   │
│    via existing scoring engine · audit trail     │
│    links every catch to source image + version   │
└──────────────────────────────────────────────────┘
```

Design principles:

- **AI extracts, code validates, humans confirm.** The LLM never writes to the
  database; validators never guess; nothing is committed without CONFIRM (WhatsApp)
  or an admin save (Streamlit).
- **Idempotent + replayable**: original image is immutable in Storage; every stage
  writes its output to the submission row, so any card can be re-processed after a
  prompt/template fix.
- Perspective-warp correction (full OpenCV homography) is **deliberately deferred**:
  vision LLMs read moderately skewed cards fine, and sample 1 (90° rotation) is
  handled by coarse rotation in preprocessing. Add dewarping only if the golden-set
  benchmark (Section 11) shows it pays.

---

## 5. Template registry (JSON)

Stored in repo at `config/scorecard_templates.json` (**built 2026-06-25** — all
three versions + UNKNOWN fallback, validated); loaded by the extraction
function; one entry per form version. The version drift is encoded as a
base entry (`WCSAA_2025_09`) with `diff_from` + `overrides` on the older two:
2024/2023 drop `U/13 ASSISTED` and label the witness column `WITNESS WCSAA No.`
(renamed to `WP No.` in 2025). Zones are *semantic regions described to the
model*, with optional crop boxes (fractions of corrected image) used to send
higher-DPI crops for the header and table separately when full-card accuracy is
insufficient.

```json
{
  "templates": [
    {
      "template_id": "WCSAA_2025_09",
      "match": { "version_text": ["Ver. Sept 2025", "Ver Sept 2025"] },
      "header_fields": [
        { "name": "wp_number",   "zone": "top-left box labelled 'WP #'", "type": "string", "pattern": "^\\d{1,5}$" },
        { "name": "angler_name", "zone": "box labelled 'Initial(s) / Surname'", "type": "string" },
        { "name": "date",        "zone": "box labelled 'DATE'", "type": "date" },
        { "name": "club",        "zone": "CLUB row of boxes", "type": "selection",
          "options": ["BR", "FB", "4/Oc", "GW", "POL", "2/Oc", "TB"],
          "mark_styles": ["circle", "tick", "cross", "shading"] },
        { "name": "division",    "zone": "DIVISION row of boxes", "type": "selection",
          "options": ["U/16", "U/21", "LADY", "SENIOR", "MASTER", "G/MASTER", "U/13 ASSISTED"] }
      ],
      "table": {
        "max_rows": 11,
        "columns": ["row_no", "species", "length_cm", "length_words",
                     "fish_sex", "witness_wp", "witness_sign_present", "time"],
        "notes": "blank rows allowed and must be omitted; witness_sign is presence-only, never OCR'd"
      },
      "crop_zones": {
        "header": [0.0, 0.0, 1.0, 0.30],
        "table":  [0.0, 0.25, 1.0, 1.0]
      }
    },
    {
      "template_id": "WCSAA_2024_10",
      "match": { "version_text": ["Ver. Oct 2024"] },
      "diff_from": "WCSAA_2025_09",
      "overrides": {
        "division_options": ["U/16", "U/21", "LADY", "SENIOR", "MASTER", "G/MASTER"],
        "witness_column_label": "WITNESS WCSAA No."
      }
    },
    {
      "template_id": "WCSAA_2023_10",
      "match": { "version_text": ["Ver. Oct 2023"] },
      "diff_from": "WCSAA_2024_10",
      "overrides": {}
    }
  ],
  "fallback": {
    "template_id": "UNKNOWN",
    "behavior": "extract best-effort, force review_required=true on all fields, alert admin to add template"
  }
}
```

New form version = new JSON entry. No retraining, no code change.

---

## 6. Validation engines (deterministic, post-extraction)

### 6.0 Row completeness gate (MANDATORY — locked 2026-06-25)
Every catch row that contains **any** data must carry **all** of the following or
it is `review_required` (never auto-accepted). These are hard gates, not soft hints:

| Field | Rule | Fail action |
|---|---|---|
| `species` | Must resolve to a canonical species via the lexicon (beach shorthand accepted — §6.2). Free text never passes. | review |
| `length_cm` | Present, numeric, within the species sanity band (§6.1). | review |
| `length_words` | **Must be completed** and must cross-check `length_cm` (§6.1). A row with a number but no words → review. | review |
| `fish_sex` | `M` or `F`. Required — and load-bearing for sexed species, where it selects the canonical `(M)`/`(F)` entry (§6.2). | review |
| `witness_wp` | **Must validate against the `anglers` roster** (exists; zero-padded `WP####`) and differ from the angler (§6.4). | review |
| `witness_sign_present` | **Must be `true` for every populated row.** A data row with no witness signature is invalid evidence → flag (do not commit). | review |
| `time` | **Must be present and parse** to `HH:mm` (§6.5). | review |

A row is auto-accept-eligible only when all seven pass *and* their confidences clear
the §7 threshold. Blank rows are omitted entirely (not gated).

### 6.1 Length cross-validation — the workhorse
Parse `length_words` ("ONE THREE FOUR", "NINTY EIGHT", "SEVENTY ONE") with a
number-word grammar that accepts both digit-naming ("ONE ZERO SEVEN" → 107) and
quantity naming ("ONE HUNDRED SEVEN", "NINETY EIGHT"), plus common misspellings
(NINTY, FOURTY, SEVENTEY). Compare to `length_cm`.
- Match → the row's length is effectively verified (two independent handwriting
  reads agreeing by accident is rare). Confidence 99.
- Mismatch → `{"row": n, "error": "length_mismatch", "cm": 134, "words_parsed": 124}`
  → review queue with the row's image context.
Sanity band per species (e.g. Kob 20–180 cm) catches absurd values.

### 6.2 Species lexicon + fuzzy match
Canonical lexicon seeded from the existing `species` table (which already drives
scoring) plus colloquial aliases:

| Written | Canonical |
|---|---|
| COW, COWSHARK | Shark (Cow) (Sevengill) |
| SANDY, SAND SHARK | Guitarfish (Bluntnose) *(club usage: "Sandy Shark")* |
| EAGLE RAY | Ray (Eagle) |
| RAGGIE, RAGGED TOOTH | Shark (Ragged Tooth) |
| SMOOTHHOUND, HOUND | Shark (Smooth Hound) |
| STEENBRAS, WHITE STEEN | Steenbras (White) |

Match = normalized Levenshtein / token-set ratio against lexicon + aliases;
confidence = scaled similarity. Below threshold (≈85) → review. **Important:** the
alias table is club-confirmable data, not code — store it in the DB so the league
secretary can extend it without a deploy.

**Beach shorthand is supported (locked 2026-06-25).** Anglers write colloquial
shorthand ("COW", "SANDY", "EAGLE RAY") and the lexicon must resolve it — free text
never reaches the scorer. The first three are seeded in `data/species_aliases.json`
(verified against `species_master.csv`); the matcher in `scripts/scoring.py` is
**case-sensitive exact** on the alias key.

**fish_sex is load-bearing, not cosmetic.** Some species exist in `species_master.csv`
*only* as `(M)`/`(F)` rows (e.g. Ragged-tooth, Smooth-hound) with **different weight
coefficients per sex** — there is no sexless entry. For these the canonical cannot be
resolved without the M/F, so the pipeline appends the captured `fish_sex` to the
species string (`RAGGIE` + `F` → `"RAGGIE (F)"`); the scorer strips the suffix,
resolves the base alias, and reattaches the sex if `"<canon> (F)"` exists in the
master (`scoring.py` `resolve()` steps 3–4). A sexed-species row with a missing/blank
M/F therefore **fails the §6.0 gate** rather than risking a wrong-coefficient score.

### 6.3 Club / division selection
The model reports `{selected, mark_style, alternatives_marked}` per selection row.
Validator rules: exactly one mark → accept (confidence from model's mark clarity);
zero or multiple marks → review. Cross-check: angler WP number's club in the roster
should equal the marked club — disagreement flags *both* fields.

### 6.4 Witness validation (MANDATORY per row — locked 2026-06-25)
- `witness_wp` **must exist in the `anglers` roster** → DB lookup (zero-pad to WP####).
  Not found → review. This is a hard requirement on every populated row, not a
  best-effort check.
- Witness must differ from the angler (a card cannot witness itself).
- `witness_sign_present` **must be `true` for every row that has catch data.** The
  signature is the evidentiary core of the card — a populated row with no witness
  signature is invalid and must not be committed; flag to review/reject.
- Signature *content*: presence detection only (`witness_sign_present: true/false`).
  v1 stores the full corrected card image + row index; cropped signature snippets are
  a v2 nicety requiring row-geometry detection — out of scope for v1 (precise per-row
  pixel crops from bent cards is the least reliable part of any design).

### 6.5 Time normalization (MANDATORY per row — locked 2026-06-25)
`time` **must be present and parse** on every populated row — a data row with no
time fails the §6.0 gate. Deterministic parser for the observed zoo: `8.40`, `8:40`,
`9 am`, `1:30PM`, `10h40`, `358` (= 3:58), bare `329`. Rules: strip spaces/dots → try
HH:mm, HhMM, H:mm AM/PM, 3-4 digit packed; afternoon inference from row order (times
must be non-decreasing down the card — a monotonicity check that also catches
misreads). Output `HH:mm` 24h. Missing or unparseable → review.

### 6.6 Header checks
- `wp_number` exists in roster; extracted `angler_name` fuzzy-matches the roster
  name for that WP (mismatch → review; catches both OCR errors and borrowed cards).
- `date` parses (multiple formats) and falls on/near a known competition date from
  the `competitions` table; date in the future or >7 days from a comp → review.

---

## 7. Confidence framework

Every field carries:

```json
{ "value": "Shark (Cow) (Sevengill)", "confidence": 98, "source_region": "table.row1.species", "review_required": false }
```

Confidence is **computed, not vibes**: start from the model's per-field self-score,
then validators override — a passed cross-check floors confidence at its strength
(length match → 99; witness WP found → +; species exact-alias hit → 97), a failed
check caps it below the review threshold. Threshold 90: anything below →
`review_required: true`. A submission auto-summarizes as: `n fields, k flagged` —
the k fields are what the human sees first.

This is how `<5%` review is reachable: on a legible card, every row can pass
length-cross-check + species-alias + witness-lookup and sail through; only
genuinely ambiguous ink reaches a person.

---

## 8. Database schema (Supabase / Postgres)

Staging-first: AI output lands in staging tables; only confirmed data is promoted
into the existing `catches_raw` → scoring pipeline.

```sql
create table scorecard_submissions (
  id              uuid primary key default gen_random_uuid(),
  season          text not null,
  source          text not null check (source in ('whatsapp','upload')),
  whatsapp_msisdn text,
  original_path   text not null,           -- Storage path, immutable
  corrected_path  text,
  template_id     text,                    -- WCSAA_2025_09 / UNKNOWN
  status          text not null default 'received'
                  check (status in ('received','processing','extracted',
                                    'awaiting_confirm','in_review','confirmed',
                                    'committed','rejected','failed')),
  wp_number       text,
  angler_name     text,
  comp_date       date,
  club            text,
  division        text,
  field_confidence jsonb,                  -- per-field confidence objects
  validation_errors jsonb,                 -- [{row, error, detail}]
  model_used      text,                    -- haiku/sonnet + version
  tokens_in       int, tokens_out int,     -- cost telemetry
  created_at      timestamptz default now(),
  confirmed_at    timestamptz,
  confirmed_by    text,                    -- msisdn or admin user
  committed_at    timestamptz
);

create table scorecard_catches (
  id              uuid primary key default gen_random_uuid(),
  submission_id   uuid not null references scorecard_submissions(id) on delete cascade,
  row_no          int not null,
  species_raw     text,                    -- exactly as written: "SANDY"
  species         text,                    -- canonical: "Guitarfish (Bluntnose)"
  species_confidence numeric,
  length_cm       numeric,
  length_words_raw text,
  length_validated boolean,
  fish_sex        text check (fish_sex in ('M','F') or fish_sex is null),
  witness_wp      text,
  witness_valid   boolean,
  witness_sign_present boolean,
  caught_at       text,                    -- normalized HH:mm
  time_valid      boolean,
  review_required boolean default false,
  corrected_by_human boolean default false,
  unique (submission_id, row_no)
);

create table species_aliases (              -- secretary-editable, drives fuzzy match
  alias           text primary key,        -- 'SANDY'
  species         text not null,           -- canonical name in species table
  added_by        text,
  created_at      timestamptz default now()
);

-- RLS enabled on all three (service_role only), consistent with 2026-06-11 hardening.
```

**Commit contract (resolved 2026-06-25).** The existing `catches_raw` table has only
**four columns** — `["comp_id", "wp_no", "species_raw", "length_cm"]` (`app_lib.py`
`DEFAULT_CATCH_COLS`); `save_catches_raw()` drops everything else and `rescore_all()`
re-derives canonical species, weight (SASAA length→weight), edible, and points. So on
confirm, each gated row maps as:

| scorecard_catches field | → catches_raw | mapping |
|---|---|---|
| header `wp_number` | `wp_no` | one header WP applies to all rows; zero-pad `WP####` |
| `comp_date` → `competitions` (or admin-selected IC) | `comp_id` | e.g. "IC 8" |
| `species` (+ `fish_sex` for sexed species) | `species_raw` | write the alias/canonical string incl. `(M)`/`(F)` so the scorer resolves it |
| `length_cm` | `length_cm` | numeric cm |

The other **mandatory §6.0 fields — `length_words`, `fish_sex` (when sexless),
`witness_wp`, `witness_sign_present`, `time` — are NOT promoted into `catches_raw`;
they live in `scorecard_catches`** (the staging table above) as the permanent evidence
+ audit record, and they **gate** the promotion (a row that fails §6.0 never reaches
`catches_raw`). In the zero-cost PoC (§14) `scorecard_catches` is a **local JSON/CSV
sidecar** rather than a Supabase table — same fields, same gate, no DB change.

No scorecard redesign or weigh-in branch is needed: capture is species + length, the
app derives weight/points/GP (Decision 1, §13).

---

## 9. API design (Supabase Edge Functions)

| Endpoint | Method | Purpose |
|---|---|---|
| `/scorecard-webhook` | POST | Meta WhatsApp webhook: receives image messages + CONFIRM/CORRECT replies. Deployed `--no-verify-jwt` (Meta can't sign Supabase JWTs — same rule as the 4OAC bot). |
| `/scorecard-process` | POST (internal) | Runs preprocess → extract → validate for one submission id. Invoked async after intake; retry-safe. |
| `/scorecard-status?id=` | GET | Submission status + extracted JSON (admin UI). |
| `/scorecard-confirm` | POST | `{id, action: confirm|reject, corrections?: [...]}` from WhatsApp reply handler or Streamlit review page. Promotes to catches on confirm. |

### WhatsApp conversation

```
Angler  → [photo of scorecard]
Bot     → 🎣 Scorecard received — processing...
Bot     → ✅ Scorecard read (Ver Sept 2025)
          WP: 0538 · Oswin Voget · 2/Oc · Senior
          Date: 17/01/2026
          11 catches: 4× Cow Shark, 6× Sandy Shark, 1× Eagle Ray
          ⚠ Row 3: length words "ONE TWO FOUR" vs 126 cm — please check
          Reply CONFIRM to submit, or CORRECT 3 124 to fix row 3.
Angler  → CORRECT 3 124
Bot     → Row 3 updated to 124 cm (words match ✓). Reply CONFIRM to submit.
Angler  → CONFIRM
Bot     → 🏆 Submitted. 11 catches recorded for IC 5 pending weigh-in.
```

Replies are state-machine driven off `scorecard_submissions.status`; the angler's
MSISDN must map to a registered member (existing 4OAC pattern: WP ↔ phone link).

### Streamlit admin: **Review queue** page
Side-by-side corrected image and editable extracted fields, flagged fields
highlighted, one-click approve/reject, audit of who corrected what. This is also
the bulk-upload path for paper cards photographed after the comp.

---

## 10. Cost model (honest numbers)

Per card: image ~1.6–2.5K tokens + prompt ~1.5K + output ~1–2K.

| Volume | Haiku-first hybrid | All-Sonnet |
|---|---|---|
| Per card | ~$0.01 | ~$0.03–0.05 |
| WCSAA season (~800 cards) | **~$8–12/yr** | ~$25–40/yr |
| Spec target 10,000/yr | ~$100–150/yr | ~$300–500/yr |

Controls from day one: monthly spend cap in the Console (hard stop), per-MSISDN
daily submission limit, token telemetry on every submission row. At WCSAA's own
volume this is beer-money; the 10K multi-org scale is where the hybrid routing
matters. **Each affiliated org should run on its own API key** (cost attribution +
blast-radius isolation).

## 11. Accuracy program (how 98% is proven, not hoped)

1. **Golden set first**: 30–50 real cards across all three versions, hand-labelled
   into the exact output JSON. This is Phase 0 and gates everything.
2. Field-level metrics per run: exact-match % per field type, review rate,
   false-accept rate (worst failure: wrong value with high confidence).
3. Tune in order: prompt wording → zone crops on/off → Haiku vs Sonnet routing →
   review threshold. Re-run golden set after every change (it's ~$2 a run).
4. Regression gate: a template/prompt change ships only if golden-set accuracy
   doesn't drop.

## 12. Integrity & governance model (added 2026-06-12)

**Principle: nobody types data, and nobody verifies their own club.** The AI is the
neutral first reader; humans judge, they don't transcribe.

Roles & flow:
1. **Club rep** — photograph + upload own club's cards within a submission window
   (e.g. 48h post-comp). No edit rights on extracted values. RLS by club. Sees own
   club's submission statuses only.
2. **Evidence chain** — original image immutable in Storage with content hash;
   every catch row permanently references card image + extraction JSON + template
   version. Duplicate image (hash) or duplicate angler+comp card auto-flagged.
3. **AI + validators** — extraction and cross-checks as per Sections 5–7; the
   scorer's queue is the flag list, not the full data set.
4. **WCSAA scorer** — side-by-side verify; approve / correct-with-reason / query
   back to rep (query thread logged). Scorer cannot be bypassed.
5. **Finalization lock** — comp finalize freezes records; later changes only via
   logged amendment (who/when/why/old/new).
6. **Four-eyes exceptions** — scorer's own club's cards need a second approver or
   spot-audit; record-class/trophy-deciding catches always require explicit human
   sign-off regardless of confidence.

Integrity analytics for the scorer (flags, never verdicts): species-length
outliers, witness signing-frequency anomalies, out-of-session times, angler
pattern deviation vs own history.

Transparency: clubs see own card statuses; the signed, witnessed card image is the
ruling artifact in any dispute; all scoring systems (current points, GP, future)
recompute from the same immutable observations.

This model is identical whether extraction runs via the $0 Claude Code batch flow
or the automated API pipeline — only the "extract" trigger differs.

## 13. Implementation roadmap

| Phase | Scope | Effort | Exit criteria |
|---|---|---|---|
| **0 — PoC + golden set** | Label 30–50 cards; single script: image → extraction JSON; measure | 2–3 sessions | ≥95% field accuracy on golden set; cost/card confirmed |
| **1 — Core pipeline + admin review** | Storage, staging tables, edge function `scorecard-process`, validators, Streamlit Review queue, bulk upload | 3–5 sessions | Admin can photo-upload a card and commit validated catches end-to-end |
| **2 — WhatsApp loop** | `scorecard-webhook`, CONFIRM/CORRECT state machine, MSISDN↔WP mapping, spend caps | 2–3 sessions | Angler submits + confirms from the beach |
| **3 — Multi-version hardening** | Template registry fallback flow, species-alias admin UI, signature snippets (zone geometry), per-org keys/templates | as needed | Unknown-version cards degrade gracefully; new org onboarded by JSON only |

**Decisions — all resolved (2026-06-25):**
1. ~~Length vs weight commit~~ **RESOLVED (2026-06-12):** capture is always
   species + length cm. A confirmed scorecard creates a `catches_raw` row with
   species + length + fish-sex; the app converts length → weight (SASAA formula,
   `scripts/scoring.py`) → points → GP. No scorecard redesign needed for GP.
2. ~~Fish-sex interpretation of MALE/FEMALE~~ **RESOLVED (2026-06-25):** confirmed —
   the column is the **fish's** sex, `M` = Male, `F` = Female. Schema field `fish_sex`
   (Section 2.4, Section 8) is correct as written; the spec's "Witness Gender" label
   was a misreading.
3. ~~WhatsApp host~~ **RESOLVED (2026-06-25):** **no WhatsApp for the PoC.** Phase 2
   (the `scorecard-webhook` + CONFIRM/CORRECT state machine) is deferred indefinitely.
   The active path is **Streamlit upload + admin review only**.
4. ~~Budget sign-off~~ **RESOLVED (2026-06-25):** **no paid budget approved — build a
   zero-cost / free-tier PoC.** See Section 14. Extraction runs via the **Claude Code
   batch flow** ($0 — no Anthropic API spend), not Supabase Edge Functions + paid API.
   The paid API pipeline (Sections 9–10) is the documented *future* upgrade once the
   PoC proves value and budget is signed off.

## 14. Zero-cost PoC plan (active path, 2026-06-25)

Constraints locked: **no paid API budget, no WhatsApp.** This narrows the active build
to the cheapest credible slice that still proves the core thesis — *can AI read these
cards accurately enough to cut manual capture?* — without spending a cent on inference
or new infrastructure.

**What changes vs the full design:**

| Concern | Full design (Sections 4–10) | Zero-cost PoC (this section) |
|---|---|---|
| Extraction trigger | Supabase Edge Function calling Anthropic API ($0.01–0.05/card) | **Claude Code batch flow** — admin drops card images in a folder; Claude Code reads them against `config/scorecard_templates.json` and emits the JSON. $0. |
| Inference cost | ~$8–40/season | **$0** (uses existing Claude Code session) |
| Hosting | Edge Functions + webhook | None new — runs locally / in the existing Streamlit app |
| WhatsApp loop | Phase 2 | **Cut** |
| Storage / staging tables | Supabase (shared prod project) | **Local first** — golden set + extraction JSON live in the repo (`scripts/`, `data/`), nothing written to Supabase until accuracy is proven |
| Validators (Section 6) | unchanged | unchanged — pure Python, no cost |
| Review UI | Streamlit Review queue | unchanged (built in Phase 1) |

**Why this is legitimate, not a toy:** Section 12 already states the integrity model is
*identical* whether extraction runs via the $0 Claude Code flow or the paid API — only
the trigger differs. The template registry, validators, confidence framework, schema,
and review UI are all reused verbatim when/if the paid pipeline is funded later.

**Zero-cost roadmap (supersedes the table in Section 13 for now):**

| Step | Scope | Cost | Exit criteria |
|---|---|---|---|
| **0 — Golden set** | Shahiem supplies 30–50 real card photos across the 3 versions; hand-label into the output JSON | $0 | Labelled set committed under `data/scorecard_golden/` |
| **1 — PoC extractor** | `scripts/scorecard_poc.py`: load a card image → (Claude Code reads it against the registry) → write extraction JSON → run the Section 6 validators → print accuracy vs golden labels | $0 | ≥95% field accuracy measured on the golden set |
| **2 — Streamlit review** | Admin "Scorecard Review" page: upload image, see extracted+validated fields, correct flagged ones, commit confirmed catches to local staging | $0 | Admin commits a validated card end-to-end, no API |
| **Later (funded)** | Promote extraction to the paid API + Edge Functions; add the WhatsApp loop | budget | only after PoC proves value |

The blocker for Step 0 is real card images — the originals shared on 2026-06-12 were
not retained (only text descriptions in `raw/notes/wcsaa-scorecard-samples-2026-06-12.md`).
