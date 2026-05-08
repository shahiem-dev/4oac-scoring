"""Theme + branding for the WCSAA League app.

Stores a colour palette in data/theme.json (per-app, season-agnostic) and
injects CSS into every page. Also exposes a Plotly-friendly palette so
analytics charts inherit the brand colours.
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
THEME_PATH = ROOT / "data" / "theme.json"


# ---- Default + presets ---------------------------------------------------

DEFAULT_THEME: dict[str, str] = {
    "main_bg":              "#F5F7FA",
    "sidebar_bg":           "#0B2545",
    "sidebar_heading":      "#FFD60A",
    "sidebar_item":         "#DDE6F0",
    "sidebar_active":       "#FFD60A",
    "sidebar_active_bg":    "#13315C",
    "page_heading":         "#0B2545",
    "section_heading":      "#13315C",
    "body_text":            "#1F2937",
    "button_bg":            "#0B2545",
    "button_text":          "#FFFFFF",
    "info_bg":              "#E8F1FF",
    "success_bg":           "#E7F8EC",
    "warning_bg":           "#FFF7DB",
    "error_bg":             "#FDE7E7",
    "metric_text":          "#0B2545",
    "leader_highlight":     "#FFF5CC",
    "chart_primary":        "#0B2545",
    "chart_accent":         "#FFD60A",
}

PRESETS: dict[str, dict[str, str]] = {
    "Ocean (Default)": DEFAULT_THEME,
    "Forest": {
        **DEFAULT_THEME,
        "sidebar_bg": "#1B4332", "sidebar_heading": "#FFD166",
        "sidebar_active_bg": "#2D6A4F", "page_heading": "#1B4332",
        "section_heading": "#2D6A4F", "button_bg": "#1B4332",
        "leader_highlight": "#FFF1C2",
        "chart_primary": "#1B4332", "chart_accent": "#FFD166",
        "main_bg": "#F4F7F4",
    },
    "Sunset": {
        **DEFAULT_THEME,
        "sidebar_bg": "#7C2D12", "sidebar_heading": "#FED7AA",
        "sidebar_active_bg": "#9A3412", "page_heading": "#7C2D12",
        "section_heading": "#9A3412", "button_bg": "#9A3412",
        "leader_highlight": "#FFEDD5",
        "chart_primary": "#9A3412", "chart_accent": "#FB923C",
        "main_bg": "#FFF7ED",
    },
    "Midnight": {
        **DEFAULT_THEME,
        "main_bg": "#0F172A", "body_text": "#E2E8F0",
        "sidebar_bg": "#020617", "sidebar_heading": "#38BDF8",
        "sidebar_item": "#CBD5E1", "sidebar_active_bg": "#1E293B",
        "page_heading": "#38BDF8", "section_heading": "#7DD3FC",
        "button_bg": "#1E293B", "button_text": "#E2E8F0",
        "info_bg": "#1E3A8A", "success_bg": "#14532D",
        "warning_bg": "#713F12", "error_bg": "#7F1D1D",
        "metric_text": "#38BDF8",
        "leader_highlight": "#1E293B",
        "chart_primary": "#38BDF8", "chart_accent": "#FACC15",
    },
    "Royal Purple": {
        **DEFAULT_THEME,
        "sidebar_bg": "#2E1065", "sidebar_heading": "#F0ABFC",
        "sidebar_active_bg": "#4C1D95", "page_heading": "#2E1065",
        "section_heading": "#5B21B6", "button_bg": "#4C1D95",
        "leader_highlight": "#F3E8FF",
        "chart_primary": "#4C1D95", "chart_accent": "#F0ABFC",
        "main_bg": "#FAF5FF",
    },
    "Steel Grey": {
        **DEFAULT_THEME,
        "sidebar_bg": "#1F2937", "sidebar_heading": "#F59E0B",
        "sidebar_active_bg": "#374151", "page_heading": "#111827",
        "section_heading": "#374151", "button_bg": "#1F2937",
        "leader_highlight": "#FEF3C7",
        "chart_primary": "#374151", "chart_accent": "#F59E0B",
        "main_bg": "#F9FAFB",
    },
}

# Deterministic Plotly palette (≥ 8 colours) used by charts.
def chart_palette(theme: dict[str, str]) -> list[str]:
    return [
        theme["chart_primary"], theme["chart_accent"],
        theme["section_heading"], theme["sidebar_active_bg"],
        "#3F88C5", "#1F7A8C", "#94A3B8", "#0EA5E9",
        "#F59E0B", "#EF4444", "#22C55E", "#A855F7",
    ]


# ---- Persistence ---------------------------------------------------------

def load_theme() -> dict[str, str]:
    if not THEME_PATH.exists():
        return dict(DEFAULT_THEME)
    try:
        data = json.loads(THEME_PATH.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_THEME)
    out = dict(DEFAULT_THEME)
    out.update({k: v for k, v in data.items() if k in DEFAULT_THEME and v})
    return out


def save_theme(theme: dict[str, str]) -> None:
    THEME_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: v for k, v in theme.items() if k in DEFAULT_THEME}
    THEME_PATH.write_text(json.dumps(clean, indent=2), encoding="utf-8")


def reset_theme() -> None:
    if THEME_PATH.exists():
        THEME_PATH.unlink()


# ---- CSS injection -------------------------------------------------------

def _component_css(t: dict[str, str]) -> str:
    """Component-library CSS — all wcsaa-* classes used by ui.py."""
    return f"""
    <style>
      /* === PAGE HEADER === */
      .wcsaa-page-header {{
        background: linear-gradient(135deg, {t['sidebar_bg']} 0%, {t['sidebar_active_bg']} 100%);
        border-radius: 12px;
        padding: 1rem 1.5rem;
        margin-bottom: 1.25rem;
        display: flex;
        align-items: center;
        gap: 0.9rem;
      }}
      .wph-icon {{ font-size: 1.8rem; line-height: 1; }}
      .wph-body {{ flex: 1; min-width: 0; }}
      .wph-title {{
        font-size: 1.45rem; font-weight: 700;
        color: {t['sidebar_heading']}; margin: 0; line-height: 1.2;
      }}
      .wph-sub {{ font-size: 0.82rem; color: rgba(255,255,255,0.70); margin-top: 3px; }}
      .wph-season {{
        background: rgba(255,255,255,0.14);
        border-radius: 20px;
        padding: 3px 13px;
        font-size: 0.77rem;
        color: {t['sidebar_heading']};
        font-weight: 600;
        white-space: nowrap;
        flex-shrink: 0;
      }}

      /* === KPI ROW === */
      .wcsaa-kpi-row {{
        display: flex; gap: 0.7rem; flex-wrap: wrap; margin-bottom: 1rem;
      }}
      .wcsaa-kpi-card {{
        flex: 1; min-width: 130px;
        background: {t['main_bg']};
        border: 1px solid rgba(0,0,0,0.08);
        border-left: 4px solid {t['chart_accent']};
        border-radius: 10px;
        padding: 0.85rem 1.1rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
      }}
      .kpi-icon {{ font-size: 1.25rem; line-height: 1; margin-bottom: 4px; }}
      .kpi-value {{
        font-size: 1.65rem; font-weight: 700;
        color: {t['metric_text']}; line-height: 1.15;
      }}
      .kpi-label {{
        font-size: 0.68rem; text-transform: uppercase;
        letter-spacing: 0.07em; color: {t['body_text']};
        opacity: 0.58; margin-top: 3px;
      }}
      .kpi-sub {{ font-size: 0.74rem; color: {t['section_heading']}; margin-top: 3px; }}

      /* === LEADER BANNER === */
      .wcsaa-leader-banner {{
        background: linear-gradient(90deg, {t['leader_highlight']} 0%, transparent 100%);
        border-left: 5px solid {t['chart_accent']};
        border-radius: 0 8px 8px 0;
        padding: 0.6rem 1rem;
        margin: 0.4rem 0 0.85rem 0;
        display: flex; align-items: center; gap: 0.75rem;
      }}
      .lb-medal {{ font-size: 1.55rem; line-height: 1; flex-shrink: 0; }}
      .lb-body {{ flex: 1; min-width: 0; }}
      .lb-name {{ font-size: 0.96rem; font-weight: 700; color: {t['page_heading']}; }}
      .lb-detail {{ font-size: 0.78rem; color: {t['body_text']}; opacity: 0.72; }}
      .lb-pts {{
        font-size: 1rem; font-weight: 700; color: {t['chart_primary']};
        background: rgba(0,0,0,0.06); padding: 3px 10px;
        border-radius: 6px; white-space: nowrap; flex-shrink: 0;
      }}

      /* === SECTION LABEL === */
      .wcsaa-section-label {{
        font-size: 0.67rem; text-transform: uppercase; letter-spacing: 0.09em;
        font-weight: 700; color: {t['section_heading']};
        border-bottom: 2px solid {t['chart_accent']};
        display: inline-block; padding-bottom: 3px;
        margin-bottom: 0.55rem; margin-top: 0.2rem;
      }}

      /* === SECTION DIVIDER WITH LABEL === */
      .wcsaa-divider {{
        display: flex; align-items: center; gap: 0.7rem;
        margin: 1.1rem 0 0.6rem 0;
      }}
      .wcsaa-divider span {{
        font-size: 0.67rem; text-transform: uppercase; letter-spacing: 0.09em;
        color: {t['section_heading']}; font-weight: 600; white-space: nowrap;
      }}
      .wcsaa-divider::before, .wcsaa-divider::after {{
        content: ''; flex: 1; height: 1px; background: rgba(0,0,0,0.10);
      }}

      /* === EMPTY STATE === */
      .wcsaa-empty {{
        text-align: center; padding: 2.25rem 1.5rem;
        color: {t['body_text']}; opacity: 0.42;
      }}
      .wcsaa-empty .ee-icon {{ font-size: 2.3rem; margin-bottom: 0.4rem; }}
      .wcsaa-empty p {{ font-size: 0.87rem; margin: 0; }}

      /* === STATUS PILL === */
      .wcsaa-pill {{
        display: inline-block; padding: 2px 9px; border-radius: 20px;
        font-size: 0.69rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.04em;
      }}
      .wcsaa-pill-ok   {{ background: {t['success_bg']}; color: #166534; }}
      .wcsaa-pill-warn {{ background: {t['warning_bg']}; color: #92400E; }}
      .wcsaa-pill-err  {{ background: {t['error_bg']}; color: #991B1B; }}

      /* === PLAIN INFO CARD === */
      .wcsaa-card {{
        background: {t['main_bg']};
        border: 1px solid rgba(0,0,0,0.08);
        border-radius: 12px;
        padding: 1.1rem 1.25rem;
        margin-bottom: 0.75rem;
        box-shadow: 0 1px 5px rgba(0,0,0,0.05);
      }}
      .wcsaa-card-header {{
        font-size: 0.88rem; font-weight: 700; color: {t['page_heading']};
        margin-bottom: 0.6rem; display: flex; align-items: center; gap: 0.4rem;
      }}

      /* === NATIVE STREAMLIT OVERRIDES === */

      /* Bordered containers */
      div[data-testid="stVerticalBlockBorderWrapper"] {{
        border-radius: 10px !important;
        border-color: rgba(0,0,0,0.09) !important;
        box-shadow: 0 1px 5px rgba(0,0,0,0.05) !important;
      }}

      /* Metric widgets */
      [data-testid="stMetric"] {{
        background: {t['main_bg']};
        border: 1px solid rgba(0,0,0,0.08);
        border-left: 4px solid {t['chart_accent']};
        border-radius: 10px;
        padding: 0.8rem 1rem !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
      }}
      [data-testid="stMetricLabel"] > div {{
        font-size: 0.69rem !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        opacity: 0.65;
      }}

      /* Tabs */
      .stTabs [data-baseweb="tab-list"] {{
        gap: 2px;
        background: rgba(0,0,0,0.03);
        border-radius: 8px 8px 0 0;
        padding: 3px 3px 0 3px;
        border-bottom: 2px solid rgba(0,0,0,0.08);
      }}
      .stTabs [data-baseweb="tab"] {{
        border-radius: 6px 6px 0 0;
        padding: 6px 18px;
        font-size: 0.83rem;
        font-weight: 500;
        color: {t['body_text']};
      }}
      .stTabs [data-baseweb="tab"]:hover {{
        background: rgba(0,0,0,0.05);
      }}

      /* Dataframe container */
      [data-testid="stDataFrame"] {{
        border-radius: 8px;
        border: 1px solid rgba(0,0,0,0.07) !important;
        overflow: hidden;
      }}

      /* Form labels */
      .stSelectbox > label,
      .stTextInput > label,
      .stNumberInput > label,
      .stTextArea > label,
      .stMultiSelect > label {{
        font-size: 0.74rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: {t['section_heading']} !important;
      }}

      /* Download button — outlined style */
      .stDownloadButton > button {{
        background-color: transparent !important;
        border: 1px solid {t['button_bg']} !important;
        color: {t['button_bg']} !important;
        font-size: 0.8rem !important;
        padding: 4px 14px !important;
      }}
      .stDownloadButton > button:hover {{
        background-color: {t['button_bg']} !important;
        color: {t['button_text']} !important;
      }}

      /* Alert rounding */
      .stAlert {{ border-radius: 8px !important; }}

      /* Mobile responsive */
      @media (max-width: 768px) {{
        .wcsaa-kpi-row {{ flex-direction: column; gap: 0.45rem; }}
        .wph-season {{ display: none !important; }}
        .wcsaa-page-header {{ padding: 0.85rem 1rem; border-radius: 8px; }}
        .wph-title {{ font-size: 1.2rem !important; }}
        .wcsaa-leader-banner {{ flex-wrap: wrap; }}
        .lb-pts {{ margin-top: 4px; }}
      }}
    </style>
    """


def _css(theme: dict[str, str]) -> str:
    t = theme
    return f"""
    <style>
      .stApp {{ background-color: {t['main_bg']}; color: {t['body_text']}; }}
      [data-testid="stSidebar"] {{ background-color: {t['sidebar_bg']}; }}
      [data-testid="stSidebar"] * {{ color: {t['sidebar_item']}; }}
      [data-testid="stSidebar"] h1,
      [data-testid="stSidebar"] h2,
      [data-testid="stSidebar"] h3,
      [data-testid="stSidebar"] h4 {{ color: {t['sidebar_heading']}; }}
      [data-testid="stSidebarNav"] a:hover {{ color: {t['sidebar_active']}; }}
      [data-testid="stSidebarNav"] a[aria-current="page"] {{
          background-color: {t['sidebar_active_bg']};
          color: {t['sidebar_active']};
          border-radius: 6px;
      }}
      h1, h2 {{ color: {t['page_heading']}; }}
      h3, h4 {{ color: {t['section_heading']}; }}
      .stButton > button {{
          background-color: {t['button_bg']};
          color: {t['button_text']};
          border: none;
          border-radius: 6px;
      }}
      .stButton > button:hover {{ filter: brightness(1.10); }}
      [data-testid="stMetricValue"] {{ color: {t['metric_text']}; font-weight: 700; }}
      .stAlert[data-baseweb="notification"] {{ border-radius: 8px; }}
      div[data-testid="stNotificationContentInfo"]    {{ background-color: {t['info_bg']}; }}
      div[data-testid="stNotificationContentSuccess"] {{ background-color: {t['success_bg']}; }}
      div[data-testid="stNotificationContentWarning"] {{ background-color: {t['warning_bg']}; }}
      div[data-testid="stNotificationContentError"]   {{ background-color: {t['error_bg']}; }}
      .stTabs [data-baseweb="tab"][aria-selected="true"] {{
          color: {t['page_heading']};
          border-bottom-color: {t['chart_accent']};
      }}

      /* Lock sidebar selectbox display text to black so it stays readable
         on any sidebar background, regardless of theme changes. Hits every
         possible BaseWeb internal element with maximum specificity. */
      section[data-testid="stSidebar"] div[data-testid="stSelectbox"],
      section[data-testid="stSidebar"] div[data-testid="stSelectbox"] *,
      section[data-testid="stSidebar"] div[data-baseweb="select"],
      section[data-testid="stSidebar"] div[data-baseweb="select"] *,
      section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
      section[data-testid="stSidebar"] div[data-baseweb="select"] > div > div,
      section[data-testid="stSidebar"] div[data-baseweb="select"] input,
      section[data-testid="stSidebar"] div[data-baseweb="select"] [class*="valueContainer"],
      section[data-testid="stSidebar"] div[data-baseweb="select"] [class*="ValueContainer"],
      section[data-testid="stSidebar"] div[data-baseweb="select"] [class*="singleValue"],
      section[data-testid="stSidebar"] div[data-baseweb="select"] [class*="SingleValue"],
      section[data-testid="stSidebar"] div[data-baseweb="select"] div[role="combobox"],
      section[data-testid="stSidebar"] div[data-baseweb="select"] div[role="combobox"] * {{
          color: #000 !important;
          -webkit-text-fill-color: #000 !important;
          opacity: 1 !important;
      }}
      /* Keep the chevron icon visible */
      section[data-testid="stSidebar"] div[data-baseweb="select"] svg {{
          fill: #000 !important;
          color: #000 !important;
      }}
      /* The label above the selectbox ("Active") inherits sidebar heading
         color — leave it. We only force the value text + chevron. */
    </style>
    """


def inject_css(theme: dict[str, str] | None = None) -> None:
    """Inject theme + component CSS into the current page. Idempotent per run."""
    t = theme or load_theme()
    st.markdown(_css(t), unsafe_allow_html=True)
    st.markdown(_component_css(t), unsafe_allow_html=True)


# ---- Plotly template helper ---------------------------------------------

def plotly_layout(theme: dict[str, str] | None = None) -> dict:
    """Layout overrides to feed into fig.update_layout(**plotly_layout())."""
    t = theme or load_theme()
    return {
        "paper_bgcolor": t["main_bg"],
        "plot_bgcolor": t["main_bg"],
        "font": {"color": t["body_text"]},
        "title_font": {"color": t["page_heading"]},
        "colorway": chart_palette(t),
    }
