"""
Fillinus Revenue Dashboard — Google Analytics style
Run: python3 -m streamlit run dashboard.py
"""

import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date
import gspread
from google.oauth2.service_account import Credentials
from groq import Groq as _Groq
from streamlit_float import float_init

# ── Google Sheets constants ───────────────────────────────────────────────────
_DIR             = os.path.dirname(os.path.abspath(__file__))
CREDS_PATH       = os.path.join(_DIR, "google-credentials.json")
SALES_MASTER_ID  = "1uWJlh4eW2RPLQFs6m3HH1RZYsgly5eTVXPacFlotQ-I"
FINANCE_MASTER_ID = "1F1V3b-tbEdP4FheVmgtQci375RPAhzUQegYGqiJZfdY"
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

def _gc():
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]), scopes=_SCOPES
        )
    else:
        creds = Credentials.from_service_account_file(CREDS_PATH, scopes=_SCOPES)
    return gspread.Client(auth=creds)

# ── Theme state (safe to read before st.set_page_config) ─────────────────────
if "theme" not in st.session_state:
    st.session_state["theme"] = "dark"
_dark = st.session_state["theme"] == "dark"

# ── Fillinus Brand Design Tokens (theme-aware) ────────────────────────────────
C_BG      = "#060D1E" if _dark else "#F2F2F2"   # Deep Navy  / Light Grey
C_SURFACE = "#0D1628" if _dark else "#FFFFFF"   # Dark card  / White card
C_SURFACE2= "#132038" if _dark else "#F5F5F5"   # Hover dark / Light hover
C_BORDER  = "#1C2B45" if _dark else "#E5E5E5"   # Dark sep   / Neutral sep
C_TEXT    = "#FCF6EE" if _dark else "#060D1E"   # Cream      / Deep Navy
C_MUTED   = "#7A8FAD" if _dark else "#4A5568"   # Blue-gray
C_BLUE    = "#1453F8"   # color/brand/blue  — invariant
C_ORANGE  = "#FF6F50"   # color/brand/orange — invariant
C_GREEN   = "#10B981"
C_RED     = "#EF4444"
C_YELLOW  = "#F59E0B"
C_LABEL   = "#C8D8F0" if _dark else "#2A3A50"   # chart bar/line labels
C_PURPLE  = "#8B5CF6"   # extended palette — warm violet, 3rd-series data
C_PINK    = "#EC4899"   # extended palette — vibrant secondary, used sparingly
C_CYAN    = "#06B6D4"   # extended palette — cool accent, 5+ series
C_SHADOW_SM = "0 1px 4px rgba(0,0,0,0.28)" if _dark else "0 1px 6px rgba(0,0,0,0.08)"
C_SHADOW_MD = "0 2px 8px rgba(0,0,0,0.30)" if _dark else "0 2px 10px rgba(0,0,0,0.09)"
PALETTE   = [C_BLUE, C_ORANGE, C_PURPLE, C_GREEN, C_YELLOW, C_PINK, C_CYAN]

# ── Chart theme ───────────────────────────────────────────────────────────────
# NOTE: no xaxis/yaxis here — pass those per-chart to avoid duplicate-kwarg error
_LAYOUT_CORE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="'DM Sans', Inter, sans-serif", color=C_TEXT, size=12),
    hoverlabel=dict(bgcolor=C_SURFACE2, bordercolor=C_BORDER, font_color=C_TEXT,
                    font=dict(family="'DM Sans', Inter, sans-serif")),
)
_MARGIN_DEF = dict(t=8, b=8, l=0, r=8)
_LEGEND_DEF = dict(
    orientation="h", yanchor="bottom", y=1.04, xanchor="left", x=0,
    bgcolor="rgba(0,0,0,0)", borderwidth=0,
)

def layout(**kw):
    """Build update_layout kwargs — merges core theme, then applies overrides.
    Accepts margin= and legend= overrides without duplicate-kwarg errors."""
    result = dict(_LAYOUT_CORE)
    result["margin"] = kw.pop("margin", _MARGIN_DEF)
    result["legend"] = kw.pop("legend", _LEGEND_DEF)
    result.update(kw)
    return result

def xax(**kw):
    base = dict(
        gridcolor="rgba(255,255,255,0.04)" if _dark else "rgba(0,0,0,0.05)",
        linecolor=C_BORDER,
        tickcolor=C_BORDER,
        tickfont=dict(color=C_TEXT, size=11),
        zeroline=False,
    )
    base.update(kw)
    return base

def yax(**kw):
    base = dict(
        gridcolor="rgba(255,255,255,0.06)" if _dark else "rgba(0,0,0,0.07)",
        linecolor="rgba(0,0,0,0)",
        zeroline=False,
        tickcolor="rgba(0,0,0,0)",
        tickfont=dict(color=C_TEXT, size=11),
    )
    base.update(kw)
    return base

PLOT_CFG = {"displayModeBar": False}

# ── AI Chat helpers ───────────────────────────────────────────────────────────
def _get_groq_client():
    try:
        key = st.secrets["groq_api_key"]
    except (KeyError, FileNotFoundError):
        key = ""
    key = key or os.environ.get("GROQ_API_KEY", "")
    if not key:
        return None
    return _Groq(api_key=key)

def _build_data_context(df: pd.DataFrame) -> str:
    today = datetime.now()
    cur_year = today.year

    lines = [f"=== FILLINUS LIVE DATA ({today.strftime('%Y-%m-%d')}) ===\n"]
    pos = df[df["net"] > 0]
    total = pos["net"].sum()

    by_year = pos.groupby("year")["net"].agg(["sum", "count"]).sort_index(ascending=False)
    lines.append("DOANH THU THEO NĂM:")
    for yr, row in by_year.iterrows():
        pct = row["sum"] / total * 100 if total else 0
        lines.append(f"  {int(yr)}: {row['sum']/1e9:.2f} tỷ ₫ ({int(row['count'])} deals, {pct:.0f}% of total)")

    lines.append(f"\nYTD {cur_year}: {pos[pos['year']==cur_year]['net'].sum()/1e9:.2f} tỷ ₫")

    top_clients = pos.groupby("client")["net"].sum().sort_values(ascending=False).head(5)
    lines.append("\nTOP 5 CLIENTS (all time):")
    for i, (client, rev) in enumerate(top_clients.items(), 1):
        n = pos[pos["client"] == client].shape[0]
        lines.append(f"  {i}. {client}: {rev/1e9:.2f} tỷ ₫ ({n} deals)")

    by_prod = pos.groupby("product")["net"].agg(["sum", "count"]).sort_values("sum", ascending=False)
    lines.append("\nPRODUCT / SERVICE MIX:")
    for prod, row in by_prod.iterrows():
        pct = row["sum"] / total * 100 if total else 0
        lines.append(f"  {prod}: {row['sum']/1e9:.2f} tỷ ({pct:.0f}%) — {int(row['count'])} deals")

    by_rep = pos[pos["year"] == cur_year].groupby("sales_rep")["net"].sum().sort_values(ascending=False)
    if not by_rep.empty:
        lines.append(f"\nSALES REP PERFORMANCE ({cur_year}):")
        for rep, rev in by_rep.items():
            lines.append(f"  {rep}: {rev/1e9:.2f} tỷ ₫")

    # Monthly breakdown — current year and previous year
    for yr in [cur_year, cur_year - 1]:
        yr_df = pos[pos["year"] == yr].copy()
        if yr_df.empty:
            continue
        yr_df["month"] = yr_df["date"].dt.month
        by_month = yr_df.groupby("month")["net"].agg(["sum", "count"]).sort_index()
        lines.append(f"\nDOANH THU THEO THÁNG — {yr}:")
        for mo, row in by_month.iterrows():
            lines.append(
                f"  Tháng {int(mo):02d}/{yr}: {row['sum']/1e6:.0f} triệu ₫"
                f" ({int(row['count'])} deals)"
            )

    # Recent 15 transactions
    recent = pos.sort_values("date", ascending=False).head(15)
    lines.append("\n15 GIAO DỊCH GẦN NHẤT:")
    for _, r in recent.iterrows():
        lines.append(
            f"  {r['date'].strftime('%d/%m/%Y')} | {r['name']} | {r['client']}"
            f" | {r['product']} | {r['net']/1e6:.0f} triệu ₫"
        )

    return "\n".join(lines)

def _chat_system_prompt(data_ctx: str) -> str:
    return f"""Bạn là Fillinus AI — trợ lý thông minh cho Fillinus Entertainment, một full-service music agency tại Việt Nam.

## Về Fillinus
- Địa chỉ: 42/30 Ung Văn Khiêm, Phường 25, Bình Thạnh, TP.HCM
- Mission: Craft impactful music solutions that amplify brands, inspire artists, and elevate productions
- Slogan: "Feeling us? Fill in us"
- Hai mảng: **Agency (B2B)** — brand sync, strategic music, production | **Entertainment (B2C)** — artist management, fan engagement
- Key metrics: 5B+ total views · 55+ happy clients · 110+ projects · 28M+ streams
- Artist roster: Bùi Công Nam, Myra Trần, Anh Tú, Erik, Nguyễn Thúc Thùy Tiên, Juky San, Mai Tiến Dũng, Tiến Luật, Hoàng Duyên, Choco Trúc Phương, Vũ Phụng Tiên, CARA, JSOL, Doãn Hiếu, Ngọc Thanh Tâm, Đỗ Hoàng Dương
- Core services: Music Strategy, Music Production, Music Partnership, Artist Management, Talent Scouting

## Dữ liệu thực tế (live từ Google Sheets):
{data_ctx}

## Hướng dẫn trả lời
- Default: Tiếng Việt. Nếu user hỏi bằng tiếng Anh → trả lời tiếng Anh.
- Format số VND: "X,X tỷ ₫" hoặc "X triệu ₫" (không dùng số raw dạng 1234567890)
- Ngắn gọn, súc tích — không padding text thừa
- Khi phân tích business: **Current State → Trend → Risk/Opportunity → Action**
- Dùng markdown (bold, list, table) khi giúp rõ hơn

## Vai trò theo câu hỏi
- **Báo cáo / số liệu**: Trích dẫn data từ FILLINUS LIVE DATA, tính toán, so sánh kỳ
- **Chiến lược**: OKRs, định hướng B2B/B2C, competitive positioning, quarterly planning
- **Marketing / Campaign**: Campaign brief, content calendar, TikTok/Facebook/YouTube strategy
- **Artist / Talent**: Match artist với brief, check roster, recommend casting
"""

def _stream_chat(client: _Groq, messages: list, system: str):
    stream = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": system}, *messages],
        stream=True,
        max_tokens=1024,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta

# ── Data fetching ─────────────────────────────────────────────────────────────
def parse_vnd(raw):
    if not raw:
        return 0.0
    s = str(raw).strip().replace("₫", "").replace(",", "").replace(" ", "")
    neg = s.startswith("(") and s.endswith(")")
    s   = s.strip("()")
    try:
        v = float(s)
        return -v if neg else v
    except ValueError:
        return 0.0

@st.cache_data(ttl=60)
def load_df():
    gc   = _gc()
    sh   = gc.open_by_key(SALES_MASTER_ID)
    ws   = sh.worksheet("Revenue")
    rows = ws.get_all_values()
    if not rows:
        return pd.DataFrame()
    headers = rows[0]
    col = {h: i for i, h in enumerate(headers)}
    recs = []
    for r in rows[1:]:
        def g(name):
            i = col.get(name, -1)
            return r[i].strip() if i >= 0 and i < len(r) else ""
        net_raw = g("Net Sales")
        recs.append({
            "name":         g("Project"),
            "project_type": g("Project Type"),
            "client":       g("Client_Name"),
            "sales_rep":    g("Sales_Rep"),
            "product":      g("Product/Service"),
            "net_raw":      net_raw,
            "net":          parse_vnd(net_raw),
            "date_str":     g("Date (auto)"),
            "is_first":     g("Project – First Date Only"),
            "new_client":   g("Client – New or Reactivated (>6 months)"),
        })
    df = pd.DataFrame(recs)
    df["date"]      = pd.to_datetime(df["date_str"], errors="coerce")
    df["year"]      = df["date"].dt.year.astype("Int64")
    df["month_str"] = df["date"].dt.strftime("%Y-%m")
    df["quarter"]   = df["date"].dt.to_period("Q").astype(str)
    return df

@st.cache_data(ttl=60)
def load_financials_df():
    gc   = _gc()
    sh   = gc.open_by_key(FINANCE_MASTER_ID)
    ws   = sh.worksheet("Bookkeeping")
    rows = ws.get_all_values()
    if not rows:
        cols = ["month","revenue","cogs","opex","cash_in","cash_out",
                "gross_profit","net_profit","cash_flow","gpm","npm"]
        return pd.DataFrame(columns=cols)

    headers = rows[0]
    col = {h: i for i, h in enumerate(headers)}
    monthly = {}

    REVENUE_CATS = {"REVENUE", "Revenue"}
    COGS_CATS    = {"COGS", "COGs"}
    OPEX_CATS    = {"G&A", "SELLING EXPENSE", "Selling"}

    for r in rows[1:]:
        def g(name):
            i = col.get(name, -1)
            return r[i].strip() if i >= 0 and i < len(r) else ""
        cat   = g("CATEGORY")
        year  = g("Year")
        month = g("Month")
        if not year or not month:
            continue
        try:
            yr = int(year); mo = int(month)
        except ValueError:
            continue
        key = f"{yr:04d}-{mo:02d}"
        if key not in monthly:
            monthly[key] = {"revenue": 0, "cogs": 0, "opex": 0,
                            "cash_in": 0, "cash_out": 0}
        cash_in  = parse_vnd(g("CASH IN"))
        cash_out = parse_vnd(g("CASH OUT"))
        monthly[key]["cash_in"]  += cash_in
        monthly[key]["cash_out"] += cash_out
        if cat in REVENUE_CATS:
            monthly[key]["revenue"] += cash_in
        elif cat in COGS_CATS:
            monthly[key]["cogs"]    += cash_out
        elif cat in OPEX_CATS:
            monthly[key]["opex"]    += cash_out

    recs = []
    for key in sorted(monthly):
        m = monthly[key]
        rev  = m["revenue"]
        cogs = m["cogs"]
        opex = m["opex"]
        gp   = rev - cogs
        np_v = rev - cogs - opex
        cf   = m["cash_in"] - m["cash_out"]
        recs.append({
            "month":        key,
            "revenue":      rev,
            "cogs":         cogs,
            "opex":         opex,
            "cash_in":      m["cash_in"],
            "cash_out":     m["cash_out"],
            "gross_profit": gp,
            "net_profit":   np_v,
            "cash_flow":    cf,
            "gpm":          (gp  / rev * 100) if rev else None,
            "npm":          (np_v / rev * 100) if rev else None,
        })
    cols = ["month","revenue","cogs","opex","cash_in","cash_out",
            "gross_profit","net_profit","cash_flow","gpm","npm"]
    fin = pd.DataFrame(recs, columns=cols) if recs else pd.DataFrame(columns=cols)
    return fin.reset_index(drop=True)

@st.cache_data(ttl=60)
def load_bookkeeping_df():
    gc   = _gc()
    sh   = gc.open_by_key(FINANCE_MASTER_ID)
    ws   = sh.worksheet("Bookkeeping")
    rows = ws.get_all_values()
    if len(rows) < 2:
        return pd.DataFrame()
    headers = rows[0]
    col = {h.strip(): i for i, h in enumerate(headers)}
    recs = []
    for r in rows[1:]:
        def g(name):
            i = col.get(name, -1)
            return r[i].strip() if 0 <= i < len(r) else ""
        year  = g("Year");  month = g("Month")
        if not year or not month:
            continue
        try:
            yr = int(year);  mo = int(float(month))
        except ValueError:
            continue
        cash_in  = parse_vnd(g("CASH IN"))
        cash_out = parse_vnd(g("CASH OUT"))
        date_raw = g("DATE") or g("Date")
        try:
            dt = pd.to_datetime(date_raw, dayfirst=True, errors="coerce")
        except Exception:
            dt = pd.NaT
        recs.append({
            "date":       dt,
            "year":       yr,
            "month":      mo,
            "month_key":  f"{yr:04d}-{mo:02d}",
            "category":   g("CATEGORY"),
            "cf_type":    g("TYPE OF CASHFLOW"),
            "description":g("DESCRIPTION"),
            "cash_in":    cash_in,
            "cash_out":   cash_out,
        })
    if not recs:
        return pd.DataFrame()
    return pd.DataFrame(recs)

# ── HTML helpers ──────────────────────────────────────────────────────────────
def fmt_b(v):   return f"{v/1e9:.2f}B ₫"
def fmt_m(v):   return f"{v/1e6:.1f}M"

def pct_badge(pct):
    if pct is None:
        return '<span style="font-size:11px;font-weight:600;color:#6B7A99;background:rgba(107,122,153,0.12);border-radius:4px;padding:2px 7px">—</span>'
    arrow = "↑" if pct >= 0 else "↓"
    color = C_GREEN if pct >= 0 else C_RED
    bg    = "rgba(16,185,129,0.12)" if pct >= 0 else "rgba(239,68,68,0.12)"
    return f'<span style="font-size:11px;font-weight:600;color:{color};background:{bg};border-radius:4px;padding:2px 7px">{arrow} {abs(pct):.1f}%</span>'

def score_card_html(label, value, badge, hint, accent=C_BLUE, tooltip="", icon=""):
    tt = f' data-tooltip="{tooltip}"' if tooltip else ""
    icon_html = f"""
      <div style="width:42px;height:42px;border-radius:10px;
                  background:{accent}22;border:1px solid {accent}33;
                  display:flex;align-items:center;justify-content:center;
                  font-size:17px;flex-shrink:0;color:{accent}">{icon}</div>
    """ if icon else ""
    return f"""
    <div{tt} style="background:{C_SURFACE};border:1px solid {C_BORDER};
                border-radius:12px;padding:20px 22px 16px;position:relative;height:100%;
                box-shadow:{C_SHADOW_SM};
                transition:box-shadow 0.2s;cursor:default;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px">
        <div style="flex:1;min-width:0">
          <div style="font-size:11px;font-weight:600;letter-spacing:0.7px;text-transform:uppercase;
                      color:{C_MUTED};margin-bottom:6px;white-space:nowrap;overflow:hidden;
                      text-overflow:ellipsis">{label}</div>
          <div style="font-size:28px;font-weight:700;color:{C_TEXT};letter-spacing:-0.8px;
                      line-height:1">{value}</div>
        </div>
        {icon_html}
      </div>
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
        {badge}
        <span style="font-size:11px;color:{C_MUTED}">{hint}</span>
      </div>
      <div style="position:absolute;bottom:0;left:16px;right:16px;height:2px;
                  background:linear-gradient(90deg,{accent},{accent}00);
                  border-radius:0 0 2px 2px;opacity:0.7"></div>
    </div>
    """

def card_header(title, sub=""):
    sub_html = (f'<span style="font-size:11px;font-weight:400;color:{C_MUTED};'
                f'letter-spacing:0.1px">{sub}</span>') if sub else ""
    return st.markdown(
        f'<div style="background:{C_SURFACE};border:1px solid {C_BORDER};border-radius:12px;'
        f'padding:18px 22px 6px;box-shadow:{C_SHADOW_SM}">'
        f'<div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:10px">'
        f'<span style="font-size:13px;font-weight:600;color:{C_TEXT};letter-spacing:0.1px">{title}</span>'
        f'{sub_html}</div>',
        unsafe_allow_html=True,
    )

def card_close():
    return st.markdown("</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG & GLOBAL CSS
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Fillinus · Revenue",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)
float_init()

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,300;1,9..40,400&display=swap');
@import url('https://fonts.googleapis.com/icon?family=Material+Icons+Round');

/* ── Page background + global text color ── */
.stApp, body {{ background: {C_BG} !important; color: {C_TEXT} !important; }}
.block-container {{ padding: 1.5rem 2rem 2rem !important; max-width: 1440px; }}
*, html, body, p, div, span, li, label, caption, small, input, button, select {{
  font-family: 'DM Sans', Inter, -apple-system, sans-serif !important;
  color: inherit;
}}
/* Force all unthemed text to use brand text color — prevents cream-on-white in light mode */
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] p,
[data-testid="stAppViewContainer"] span,
[data-testid="stAppViewContainer"] div,
[data-testid="stAppViewContainer"] li,
[data-testid="stAppViewContainer"] label {{
  color: {C_TEXT};
}}

/* ── Sidebar ── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div,
section[data-testid="stSidebar"] > div > div {{
  background: {C_SURFACE} !important;
}}
section[data-testid="stSidebar"] {{
  border-right: 1px solid {C_BORDER} !important;
}}
/* Sidebar text */
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] small {{
  color: {C_TEXT} !important;
}}
/* Sidebar inputs */
section[data-testid="stSidebar"] input {{
  background: {C_SURFACE2} !important;
  border-color: {C_BORDER} !important;
  color: {C_TEXT} !important;
}}
section[data-testid="stSidebar"] [data-baseweb="select"] > div {{
  background: {C_SURFACE2} !important;
  border-color: {C_BORDER} !important;
  color: {C_TEXT} !important;
}}
/* Multiselect tags */
section[data-testid="stSidebar"] .stMultiSelect [data-baseweb="tag"] {{
  background: rgba(20,83,248,0.15) !important;
  border: 1px solid rgba(20,83,248,0.3) !important;
}}
section[data-testid="stSidebar"] .stMultiSelect [data-baseweb="tag"] span {{
  color: {C_BLUE} !important;
}}
/* Sidebar divider */
section[data-testid="stSidebar"] hr {{
  border-color: {C_BORDER} !important;
  opacity: 1 !important;
}}
/* Sidebar toggle button */
section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebarCollapseButton"] button {{
  background: {C_BLUE} !important;
  border: none !important;
  border-radius: 10px !important;
  width: 136px !important;
  height: 40px !important;
  min-width: 136px !important;
  cursor: pointer !important;
  box-shadow: 0 2px 8px rgba(20,83,248,0.30) !important;
}}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{
  background: {C_SURFACE};
  border-radius: 10px;
  padding: 4px;
  gap: 2px;
  border: 1px solid {C_BORDER};
}}
.stTabs [data-baseweb="tab"] {{
  border-radius: 8px;
  padding: 7px 20px;
  font-size: 13px;
  font-weight: 500;
  color: {C_MUTED};
  letter-spacing: 0.1px;
}}
.stTabs [aria-selected="true"] {{
  background: rgba(20,83,248,0.14) !important;
  color: {C_BLUE} !important;
  font-weight: 600 !important;
}}
.stTabs [data-baseweb="tab-border"] {{ display: none; }}
.stTabs [data-baseweb="tab-panel"] {{ padding-top: 16px !important; }}

/* ── st.metric fallback ── */
div[data-testid="stMetric"] {{
  background: {C_SURFACE};
  border: 1px solid {C_BORDER};
  border-radius: 12px;
  padding: 16px 20px;
}}

/* ── Inputs ── */
div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] > div > div {{
  background: {C_SURFACE2} !important;
  border-color: {C_BORDER} !important;
  color: {C_TEXT} !important;
  border-radius: 8px !important;
}}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: {C_BG}; }}
::-webkit-scrollbar-thumb {{ background: {C_BORDER}; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {C_MUTED}; }}

/* ── Live dot ── */
.live-dot {{
  display: inline-block;
  width: 7px; height: 7px;
  background: {C_GREEN};
  border-radius: 50%;
  animation: pulse 2s infinite;
}}
@keyframes pulse {{
  0%,100% {{ opacity:1; box-shadow:0 0 0 0 rgba(16,185,129,0.4); }}
  50%      {{ opacity:0.7; box-shadow:0 0 0 5px rgba(16,185,129,0); }}
}}

/* ── Tooltips ── */
[data-tooltip] {{ position: relative; }}
[data-tooltip]::after {{
  content: attr(data-tooltip);
  position: absolute;
  top: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: {C_BG};
  color: {C_TEXT};
  border: 1px solid {C_BORDER};
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 11.5px;
  line-height: 1.65;
  white-space: normal;
  max-width: 250px;
  min-width: 180px;
  z-index: 9999;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
  box-shadow: 0 8px 24px rgba(0,0,0,0.6);
  text-align: left;
  font-weight: 400;
  letter-spacing: 0.1px;
}}
[data-tooltip]:hover::after {{ opacity: 1; }}

/* ── Plotly chart text — override Streamlit dark-theme SVG injection ── */
[data-testid="stPlotlyChart"] .xtick > text,
[data-testid="stPlotlyChart"] .ytick > text,
[data-testid="stPlotlyChart"] .g-xtitle text,
[data-testid="stPlotlyChart"] .g-ytitle text,
[data-testid="stPlotlyChart"] .legendtext {{
  fill: {C_TEXT} !important;
}}
/* Pie/Donut labels */
[data-testid="stPlotlyChart"] .pielabel text,
[data-testid="stPlotlyChart"] .pie text {{
  fill: {C_TEXT} !important;
}}
/* Heatmap cell annotations */
[data-testid="stPlotlyChart"] .heatmap text,
[data-testid="stPlotlyChart"] .hmtext {{
  fill: {C_TEXT} !important;
}}
/* Colorbar tick labels */
[data-testid="stPlotlyChart"] .cbtick > text,
[data-testid="stPlotlyChart"] .cbaxis text {{
  fill: {C_MUTED} !important;
}}

/* ── Dataframe — theme-aware background + text ── */
[data-testid="stDataFrame"] {{
  color: {C_TEXT} !important;
  background: {C_SURFACE} !important;
  border-radius: 10px !important;
  border: 1px solid {C_BORDER} !important;
  overflow: hidden !important;
}}
[data-testid="stDataFrame"] > div,
[data-testid="stDataFrame"] > div > div {{
  background: {C_SURFACE} !important;
}}
[data-testid="stDataFrame"] [role="gridcell"],
[data-testid="stDataFrame"] [role="columnheader"] {{
  color: {C_TEXT} !important;
  background: {C_SURFACE} !important;
}}
[data-testid="stDataFrame"] [role="columnheader"] {{
  background: {C_SURFACE2} !important;
  border-bottom: 1px solid {C_BORDER} !important;
}}

/* ── Float AI chat ── */
[data-testid="stChatMessage"] {{
  background: {C_SURFACE} !important;
  border: 1px solid {C_BORDER} !important;
  border-radius: 10px !important;
  padding: 10px 14px !important;
  margin-bottom: 6px !important;
}}
[data-testid="stChatMessage"][aria-label="user message"] {{
  background: rgba(20,83,248,0.07) !important;
  border-color: rgba(20,83,248,0.18) !important;
}}

/* ── Float chat form & buttons ── */

/* Chat text input */
[data-testid="stTextInput"] input {{
  background: {C_SURFACE2} !important;
  border: 1px solid {C_BORDER} !important;
  border-radius: 10px !important;
  color: {C_TEXT} !important;
  font-size: 13px !important;
}}
[data-testid="stTextInput"] input::placeholder {{
  color: {C_MUTED} !important;
}}

/* Form container — remove default border/bg */
[data-testid="stForm"] {{
  border: none !important;
  background: transparent !important;
  padding: 0 !important;
}}

/* Send → button */
[data-testid="stFormSubmitButton"] > button {{
  background: {C_BLUE} !important;
  color: #FCF6EE !important;
  border: none !important;
  border-radius: 10px !important;
  font-size: 18px !important;
  font-weight: 700 !important;
  min-height: 38px !important;
  padding: 0 !important;
  width: 100% !important;
  box-shadow: 0 2px 8px rgba(20,83,248,0.3) !important;
}}
[data-testid="stFormSubmitButton"] > button:hover {{
  background: #0f44e0 !important;
  border: none !important;
  opacity: 1 !important;
}}

/* FAB toggle — circular */
button[kind="primary"] {{
  width: 52px !important;
  height: 52px !important;
  min-height: 52px !important;
  border-radius: 26px !important;
  padding: 0 !important;
  font-size: 20px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  box-shadow: 0 4px 20px rgba(20,83,248,0.45) !important;
}}

/* Icon buttons: ✕ close, ↺ clear */
button[kind="secondary"] {{
  background: transparent !important;
  border: 1px solid {C_BORDER} !important;
  color: {C_MUTED} !important;
  border-radius: 8px !important;
  font-size: 13px !important;
  min-height: 30px !important;
  height: 30px !important;
  padding: 0 6px !important;
  line-height: 1 !important;
}}
button[kind="secondary"]:hover {{
  background: {C_SURFACE2} !important;
  color: {C_TEXT} !important;
  border-color: {C_MUTED} !important;
}}

</style>
""", unsafe_allow_html=True)

# ── Topbar ────────────────────────────────────────────────────────────────────
last_loaded = datetime.now().strftime("%d/%m/%Y %H:%M")

st.markdown(
    f'<div style="display:flex;align-items:center;justify-content:space-between;'
    f'padding:16px 24px;background:{C_SURFACE};border:1px solid {C_BORDER};'
    f'border-radius:14px;margin-bottom:20px;box-shadow:{C_SHADOW_MD}">'

    # Left — wordmark
    f'<div style="display:flex;align-items:center;gap:14px">'
    f'<div style="width:36px;height:36px;background:{C_BLUE};border-radius:8px;'
    f'display:flex;align-items:center;justify-content:center;'
    f'font-size:16px;font-weight:800;color:#FCF6EE;letter-spacing:-0.5px;flex-shrink:0">F</div>'
    f'<div>'
    f'<div style="font-size:16px;font-weight:700;color:{C_TEXT};letter-spacing:-0.3px;line-height:1.1">'
    f'Fillinus</div>'
    f'<div style="font-size:11px;color:{C_MUTED};letter-spacing:0.2px;margin-top:1px">'
    f'Revenue Dashboard · Projects &amp; Contracts</div>'
    f'</div>'
    f'</div>'

    # Right — live badge + timestamp
    f'<div style="display:flex;align-items:center;gap:12px">'
    f'<div style="text-align:right">'
    f'<div style="font-size:11px;color:{C_MUTED}">'
    f'Updated <span style="color:{C_TEXT};font-weight:500">{last_loaded}</span></div>'
    f'</div>'
    f'<span style="font-size:11px;font-weight:600;color:{C_GREEN};'
    f'background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.25);'
    f'border-radius:20px;padding:5px 12px;white-space:nowrap">'
    f'<span class="live-dot" style="margin-right:5px"></span>Live · Sheets</span>'
    f'</div>'

    f'</div>',
    unsafe_allow_html=True,
)

# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner("Fetching from Google Sheets..."):
    df = load_df()

if df.empty:
    st.error("Cannot load data. Check Google Sheets credentials / spreadsheet ID.")
    st.stop()

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    # Theme toggle
    _is_light = st.session_state.get("theme", "dark") == "light"
    _new_light = st.toggle("☀️  Light mode", value=_is_light, key="theme_toggle")
    _new_theme  = "light" if _new_light else "dark"
    if _new_theme != st.session_state.theme:
        st.session_state.theme = _new_theme
        st.rerun()

    st.divider()

    st.markdown(f"<p style='font-size:13px;font-weight:600;color:{C_TEXT};margin-bottom:12px'>Filters</p>",
                unsafe_allow_html=True)

    min_d = df["date"].min().date() if not df["date"].isna().all() else date(2021, 1, 1)
    max_d = df["date"].max().date() if not df["date"].isna().all() else date.today()
    date_range = st.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)

    all_years = sorted(df["year"].dropna().unique().astype(int).tolist())
    sel_years = st.multiselect("Year", all_years, default=all_years)

    all_types = sorted([t for t in df["project_type"].dropna().unique() if t])
    sel_types = st.multiselect("Project type", all_types, default=all_types)

    all_prods = sorted([p for p in df["product"].dropna().unique() if p])
    sel_prods = st.multiselect("Product / Service", all_prods, default=all_prods)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("↺  Refresh data", use_container_width=False):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"{len(df)} total rows in DB")

# Apply filters
dff = df.copy()
if len(date_range) == 2:
    d0 = pd.Timestamp(date_range[0])
    d1 = pd.Timestamp(date_range[1])
    dff = dff[(dff["date"] >= d0) & (dff["date"] <= d1)]
if sel_years:
    dff = dff[dff["year"].isin(sel_years)]
if sel_types:
    dff = dff[dff["project_type"].isin(sel_types)]
if sel_prods:
    dff = dff[dff["product"].isin(sel_prods)]

# ── KPI computation ───────────────────────────────────────────────────────────
today      = datetime.now()
cur_year   = today.year
prev_year  = cur_year - 1

rev_total  = dff["net"].sum()
rev_cur    = dff[dff["year"] == cur_year]["net"].sum()
rev_prev_ytd = df[
    (df["year"] == prev_year) & (df["date"].dt.month <= today.month)
]["net"].sum()
ytd_pct = ((rev_cur / rev_prev_ytd) - 1) * 100 if rev_prev_ytd else None

cur_clients  = dff[dff["year"] == cur_year]["client"].nunique()
prev_clients = df[df["year"] == prev_year]["client"].nunique()
clients_pct  = ((cur_clients / prev_clients) - 1) * 100 if prev_clients else None

new_cl     = dff[dff["new_client"] == "TRUE"]["client"].nunique()
prev_new   = df[(df["year"] == prev_year) & (df["new_client"] == "TRUE")]["client"].nunique()
new_pct    = ((new_cl / prev_new) - 1) * 100 if prev_new else None

pos_deals  = dff[dff["net"] > 0]
avg_deal   = pos_deals["net"].mean() if len(pos_deals) else 0
prev_pos   = df[(df["year"] == prev_year) & (df["net"] > 0)]
prev_avg   = prev_pos["net"].mean() if len(prev_pos) else 0
avg_pct    = ((avg_deal / prev_avg) - 1) * 100 if prev_avg else None

# CLV — average lifetime revenue per unique client (filtered period)
clv_series  = dff[dff["client"] != ""].groupby("client")["net"].sum()
clv         = float(clv_series.mean()) if len(clv_series) > 0 else 0.0

# CRR — % of prev_year clients who also appear in cur_year (unfiltered)
_c_prev = set(df[(df["year"] == prev_year) & (df["client"] != "")]["client"].unique())
_c_cur  = set(df[(df["year"] == cur_year)  & (df["client"] != "")]["client"].unique())
retained       = len(_c_prev & _c_cur)
crr            = (retained / len(_c_prev) * 100) if _c_prev else None
clients_prev_yr = _c_prev

# Repeat revenue ratio (filtered period)
ret_rev    = dff[dff["new_client"] == "FALSE"]["net"].sum()
new_rev_kpi = dff[dff["new_client"] == "TRUE"]["net"].sum()
repeat_pct = (ret_rev / (ret_rev + new_rev_kpi) * 100) if (ret_rev + new_rev_kpi) > 0 else 0.0

# ── Score cards (4 columns via st.columns) ───────────────────────────────────
k1, k2, k3, k4 = st.columns(4, gap="small")
k1.markdown(score_card_html("Total Revenue", fmt_b(rev_total), pct_badge(ytd_pct), f"{len(dff)} transactions", C_BLUE,
    tooltip="Tổng doanh thu của tất cả giao dịch trong khoảng filter đang áp dụng. Badge ↑/↓ so với cùng kỳ năm ngoái (YTD).",
    icon="₫"), unsafe_allow_html=True)
k2.markdown(score_card_html(f"{cur_year} YTD", fmt_b(rev_cur), pct_badge(ytd_pct), f"vs {prev_year} same period", C_BLUE,
    tooltip=f"Doanh thu từ đầu năm {cur_year} đến tháng hiện tại, so với cùng kỳ năm {prev_year}. % badge = tốc độ tăng trưởng YTD.",
    icon="↗"), unsafe_allow_html=True)
k3.markdown(score_card_html("Active Clients", str(cur_clients), pct_badge(clients_pct), f"vs {prev_clients} in {prev_year}", C_ORANGE,
    tooltip=f"Số khách hàng duy nhất có giao dịch trong năm {cur_year}. So sánh với {prev_clients} clients năm {prev_year}.",
    icon="◎"), unsafe_allow_html=True)
k4.markdown(score_card_html("Avg Deal Size", fmt_m(avg_deal), pct_badge(avg_pct), f"vs {fmt_m(prev_avg)} in {prev_year}", C_PURPLE,
    tooltip=f"Giá trị trung bình mỗi giao dịch (chỉ tính deal > 0 trong khoảng filter). So sánh với trung bình năm {prev_year}.",
    icon="◈"), unsafe_allow_html=True)

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_overview, tab_kpis, tab_cashflow, tab_clients, tab_products, tab_data = st.tabs([
    "  Overview  ", "  KPIs  ", "  Cash Flow  ", "  Clients  ", "  Products & Reps  ", "  Transactions  "
])

# ════════════════════════════════════ OVERVIEW ════════════════════════════════
with tab_overview:

    # Monthly area chart ──────────────────────────────────────────────────────
    by_month = (
        dff.dropna(subset=["date"])
           .groupby("month_str")["net"].sum()
           .reset_index().sort_values("month_str")
    )
    by_month["M"]   = by_month["net"] / 1e6
    by_month["MA3"] = by_month["M"].rolling(3, min_periods=1).mean()

    fig_area = go.Figure()
    fig_area.add_trace(go.Scatter(
        x=by_month["month_str"], y=by_month["M"],
        fill="tozeroy", fillcolor="rgba(20,83,248,0.10)",
        line=dict(color=C_BLUE, width=2),
        name="Monthly",
        hovertemplate="<b>%{x}</b><br>%{y:.1f}M ₫<extra></extra>",
        mode="lines",
    ))
    fig_area.add_trace(go.Scatter(
        x=by_month["month_str"], y=by_month["MA3"],
        line=dict(color=C_ORANGE, width=1.5, dash="dot"),
        name="3-Month MA",
        hovertemplate="MA: %{y:.1f}M ₫<extra></extra>",
        mode="lines",
    ))
    fig_area.update_layout(
        **layout(), height=270,
        xaxis=xax(tickangle=-35, nticks=24),
        yaxis=yax(title="triệu ₫"),
    )

    card_header("Revenue Over Time",
                f"{by_month['month_str'].min()} → {by_month['month_str'].max()}")
    st.plotly_chart(fig_area, width="stretch", config=PLOT_CFG)
    card_close()

    # Annual + Quarterly ──────────────────────────────────────────────────────
    col_a, col_b = st.columns(2, gap="medium")

    with col_a:
        by_year = (
            dff.groupby("year")["net"].sum()
               .reset_index().sort_values("year")
        )
        by_year["B"]     = by_year["net"] / 1e9
        by_year["label"] = by_year["B"].map(lambda x: f"{x:.2f}B")
        colors_yr = [C_BLUE if i == len(by_year)-1 else "rgba(20,83,248,0.40)"
                     for i in range(len(by_year))]
        fig_yr = go.Figure(go.Bar(
            x=by_year["year"].astype(str), y=by_year["B"],
            marker_color=colors_yr, marker_line_width=0,
            text=by_year["label"], textposition="outside",
            textfont=dict(size=10, color=C_LABEL),
            hovertemplate="<b>%{x}</b><br>%{y:.2f}B ₫<extra></extra>",
        ))
        fig_yr.update_layout(
            **layout(), height=230, showlegend=False, bargap=0.35,
            xaxis=xax(type="category"),
            yaxis=yax(),
        )
        card_header("Annual Revenue", "Current year highlighted")
        st.plotly_chart(fig_yr, width="stretch", config=PLOT_CFG)
        card_close()

    with col_b:
        by_q = (
            dff.dropna(subset=["quarter"])
               .groupby("quarter")["net"].sum()
               .reset_index().sort_values("quarter").tail(12)
        )
        by_q["M"]     = by_q["net"] / 1e6
        by_q["label"] = by_q["M"].map(lambda x: f"{x:.0f}M")
        fig_q = go.Figure(go.Bar(
            x=by_q["quarter"], y=by_q["M"],
            marker_color=C_ORANGE, marker_line_width=0, opacity=0.8,
            text=by_q["label"], textposition="outside",
            textfont=dict(size=9, color=C_LABEL),
            hovertemplate="<b>%{x}</b><br>%{y:.0f}M ₫<extra></extra>",
        ))
        fig_q.update_layout(
            **layout(), height=230, showlegend=False, bargap=0.3,
            xaxis=xax(tickangle=-30),
            yaxis=yax(),
        )
        card_header("Quarterly Revenue", "Last 12 quarters")
        st.plotly_chart(fig_q, width="stretch", config=PLOT_CFG)
        card_close()

    # Year-over-Year ──────────────────────────────────────────────────────────
    yrs_cmp = sorted(dff["year"].dropna().unique().astype(int).tolist())[-4:]
    m_pivot = (
        dff[dff["year"].isin(yrs_cmp)]
           .dropna(subset=["date"])
           .assign(m=lambda d: d["date"].dt.month)
           .groupby(["year", "m"])["net"].sum().reset_index()
    )
    MONTH_LBL = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    colors_yoy = ["rgba(107,122,153,0.5)", "rgba(20,83,248,0.35)", "rgba(20,83,248,0.65)", C_BLUE]
    fig_yoy = go.Figure()
    for i, yr in enumerate(yrs_cmp):
        yd = m_pivot[m_pivot["year"] == yr].sort_values("m")
        fig_yoy.add_trace(go.Scatter(
            x=yd["m"], y=yd["net"] / 1e6,
            name=str(yr),
            line=dict(color=colors_yoy[i % len(colors_yoy)],
                      width=2.5 if yr == cur_year else 1.5),
            mode="lines+markers", marker=dict(size=4),
            hovertemplate=f"<b>{yr}</b> %{{x}}<br>%{{y:.1f}}M ₫<extra></extra>",
        ))
    fig_yoy.update_layout(
        **layout(), height=250,
        xaxis=xax(tickvals=list(range(1,13)), ticktext=MONTH_LBL),
        yaxis=yax(title="triệu ₫"),
    )
    card_header("Year-over-Year Comparison", "Monthly revenue per year")
    st.plotly_chart(fig_yoy, width="stretch", config=PLOT_CFG)
    card_close()


# ══════════════════════════════════════ KPIs ═════════════════════════════════
with tab_kpis:

    fin_df   = load_financials_df()
    if not fin_df.empty:
        fin_df["_year"] = fin_df["month"].str[:4].astype(int)
        if sel_years:
            fin_df = fin_df[fin_df["_year"].isin(sel_years)]
        if len(date_range) == 2:
            d0_str = date_range[0].strftime("%Y-%m")
            d1_str = date_range[1].strftime("%Y-%m")
            fin_df = fin_df[(fin_df["month"] >= d0_str) & (fin_df["month"] <= d1_str)]
        fin_df = fin_df.drop(columns=["_year"]).reset_index(drop=True)
    has_fin  = not fin_df.empty

    # ── Section 1: Financial Health ───────────────────────────────────────────
    st.markdown(
        f'<div style="font-size:12px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;'
        f'color:{C_MUTED};margin-bottom:12px">Tài chính & Sinh lời</div>',
        unsafe_allow_html=True,
    )

    if has_fin:
        latest    = fin_df.iloc[-1]
        avg_gpm   = fin_df["gpm"].dropna().mean()
        avg_npm   = fin_df["npm"].dropna().mean()
        total_np  = fin_df["net_profit"].sum()
        total_cf  = fin_df["cash_flow"].sum()

        f1, f2, f3, f4 = st.columns(4, gap="small")
        gpm_val = f"{latest['gpm']:.1f}%" if latest["gpm"] is not None else "—"
        npm_val = f"{latest['npm']:.1f}%" if latest["npm"] is not None else "—"
        f1.markdown(score_card_html("Gross Profit Margin", gpm_val,
            f'<span style="font-size:11px;color:{C_MUTED}">Avg {avg_gpm:.1f}%</span>',
            f"Tháng {latest['month']}", C_GREEN,
            tooltip=f"GPM = (Revenue − COGS) ÷ Revenue. Đo hiệu quả trực tiếp của sản xuất & dịch vụ. Trung bình {avg_gpm:.1f}% trong khoảng filter. Mức tốt: > 50%.",
            icon="%"), unsafe_allow_html=True)
        f2.markdown(score_card_html("Net Profit Margin", npm_val,
            f'<span style="font-size:11px;color:{C_MUTED}">Avg {avg_npm:.1f}%</span>',
            f"Tháng {latest['month']}", C_BLUE,
            tooltip=f"NPM = (Revenue − COGS − OpEx) ÷ Revenue. Lợi nhuận ròng sau toàn bộ chi phí. Trung bình {avg_npm:.1f}% trong khoảng filter. Mức tốt: > 15%.",
            icon="◑"), unsafe_allow_html=True)
        f3.markdown(score_card_html("Net Profit (Tổng)", fmt_m(total_np),
            pct_badge(None), f"{len(fin_df)} tháng ghi nhận", C_PURPLE,
            tooltip=f"Tổng lợi nhuận ròng = Revenue − COGS − OpEx cộng dồn qua {len(fin_df)} tháng trong khoảng filter. Đơn vị: triệu ₫.",
            icon="◆"), unsafe_allow_html=True)
        cf_color = C_GREEN if total_cf >= 0 else C_RED
        f4.markdown(score_card_html("Net Cash Flow", fmt_m(total_cf),
            pct_badge(None), "Cash In − Cash Out", cf_color,
            tooltip="Dòng tiền ròng = tổng Cash In − Cash Out thực tế qua tài khoản. Khác lợi nhuận kế toán: đây là tiền mặt thực, phản ánh sức khỏe thanh khoản.",
            icon="⇄"), unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        fc1, fc2 = st.columns(2, gap="medium")
        with fc1:
            fig_margin = go.Figure()
            fig_margin.add_trace(go.Scatter(
                x=fin_df["month"], y=fin_df["gpm"],
                name="GPM %", line=dict(color=C_GREEN, width=2),
                mode="lines+markers", marker=dict(size=5),
                hovertemplate="<b>%{x}</b><br>GPM: %{y:.1f}%<extra></extra>",
            ))
            fig_margin.add_trace(go.Scatter(
                x=fin_df["month"], y=fin_df["npm"],
                name="NPM %", line=dict(color=C_BLUE, width=2),
                mode="lines+markers", marker=dict(size=5),
                hovertemplate="<b>%{x}</b><br>NPM: %{y:.1f}%<extra></extra>",
            ))
            fig_margin.update_layout(
                **layout(), height=220,
                xaxis=xax(tickangle=-30),
                yaxis=yax(title="%"),
            )
            card_header("Gross & Net Margin Trend", "Monthly %")
            st.plotly_chart(fig_margin, width="stretch", config=PLOT_CFG)
            card_close()

        with fc2:
            cf_colors = [C_GREEN if v >= 0 else C_RED for v in fin_df["cash_flow"]]
            fig_cf = go.Figure(go.Bar(
                x=fin_df["month"], y=fin_df["cash_flow"] / 1e6,
                marker_color=cf_colors, marker_line_width=0,
                text=fin_df["cash_flow"].map(lambda x: f"{x/1e6:.0f}M"),
                textposition="outside", textfont=dict(size=10, color=C_LABEL),
                hovertemplate="<b>%{x}</b><br>%{y:.0f}M ₫<extra></extra>",
            ))
            fig_cf.update_layout(
                **layout(), height=220, showlegend=False, bargap=0.3,
                xaxis=xax(tickangle=-30),
                yaxis=yax(title="triệu ₫"),
            )
            card_header("Net Cash Flow by Month", "Cash In − Cash Out · xanh=dương, đỏ=âm")
            st.plotly_chart(fig_cf, width="stretch", config=PLOT_CFG)
            card_close()

    else:
        f1, f2, f3, f4 = st.columns(4, gap="small")
        for col, lbl in zip([f1,f2,f3,f4],
                            ["Gross Profit Margin","Net Profit Margin","Net Profit","Cash Flow"]):
            col.markdown(score_card_html(lbl, "—", pct_badge(None),
                "Nhập Monthly Financials", C_MUTED), unsafe_allow_html=True)
        st.markdown(
            f'<div style="background:rgba(107,122,153,0.08);border:1px solid {C_BORDER};'
            f'border-radius:8px;padding:14px 18px;margin-top:14px;font-size:12px;color:{C_MUTED}">'
            f'📋 <b>Chưa có dữ liệu Monthly Financials.</b> '
            f'Mở database <b>Monthly Financials</b> trong Notion và nhập dữ liệu mỗi tháng.<br><br>'
            f'<b>Cột cần nhập:</b><br>'
            f'• <code>Month</code> — "2026-06"<br>'
            f'• <code>Revenue_VND</code> — Doanh thu tháng (từ Projects & Contracts)<br>'
            f'• <code>COGS_VND</code> — Chi phí trực tiếp (studio, session fee, nhân công dự án)<br>'
            f'• <code>OpEx_VND</code> — Chi phí vận hành (lương, văn phòng, phần mềm, marketing)<br>'
            f'• <code>Cash_In</code> — Tiền thực nhận vào tài khoản<br>'
            f'• <code>Cash_Out</code> — Tiền thực chi ra</div>',
            unsafe_allow_html=True,
        )

    # ── Divider ───────────────────────────────────────────────────────────────
    st.markdown(
        f'<div style="height:3px;background:{C_BORDER};border-radius:2px;margin:20px 0"></div>',
        unsafe_allow_html=True,
    )

    # ── Section 2: Customer Metrics ───────────────────────────────────────────
    st.markdown(
        f'<div style="font-size:12px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;'
        f'color:{C_MUTED};margin-bottom:12px">Khách hàng & Tiếp thị</div>',
        unsafe_allow_html=True,
    )

    cm1, cm2, cm3 = st.columns(3, gap="small")
    unique_clients = dff[dff["client"] != ""]["client"].nunique()
    cm1.markdown(score_card_html("CLV — Avg / Client",
        fmt_m(clv), pct_badge(None),
        f"Trên {unique_clients} clients · filtered", C_BLUE,
        tooltip=f"Customer Lifetime Value: trung bình doanh thu mỗi khách hàng trong khoảng filter ({unique_clients} clients). Chỉ số càng cao = từng khách hàng càng có giá trị cao.",
        icon="★"), unsafe_allow_html=True)

    crr_text = f"{crr:.1f}%" if crr is not None else "—"
    crr_hint = (f"{retained} retained / {len(clients_prev_yr)} clients {prev_year}"
                if crr is not None else f"Cần data từ {prev_year}")
    cm2.markdown(score_card_html(f"CRR {prev_year}→{cur_year}",
        crr_text, pct_badge(None), crr_hint, C_GREEN,
        tooltip=f"Client Retention Rate: % khách hàng có giao dịch năm {prev_year} tiếp tục quay lại trong {cur_year}. Mục tiêu > 60%. Tính trên toàn bộ data, không bị ảnh hưởng bởi filter.",
        icon="↻"), unsafe_allow_html=True)

    cm3.markdown(score_card_html("Repeat Revenue %",
        f"{repeat_pct:.1f}%", pct_badge(None),
        f"vs {100-repeat_pct:.1f}% new · filtered period", C_ORANGE,
        tooltip="% doanh thu từ khách hàng quay lại (Returning) trong khoảng filter. Tỷ lệ cao cho thấy revenue ổn định và ít phụ thuộc vào khách mới. Mục tiêu: > 60%.",
        icon="⟳"), unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # New vs Returning revenue stacked bar by year
    nr_df = (
        dff[dff["new_client"].isin(["TRUE","FALSE"])]
           .groupby(["year","new_client"])["net"].sum()
           .reset_index()
    )
    fig_nr = go.Figure()
    for flag, label, color in [
        ("FALSE", "Returning Client", C_BLUE),
        ("TRUE",  "New / Reactivated", C_GREEN),
    ]:
        yd = nr_df[nr_df["new_client"] == flag].sort_values("year")
        fig_nr.add_trace(go.Bar(
            x=yd["year"].astype(str), y=yd["net"] / 1e6,
            name=label, marker_color=color, marker_line_width=0, opacity=0.85,
            hovertemplate=f"<b>{label}</b> %{{x}}<br>%{{y:.0f}}M ₫<extra></extra>",
        ))
    fig_nr.update_layout(
        **layout(), height=230, barmode="stack", bargap=0.3,
        xaxis=xax(type="category"),
        yaxis=yax(title="triệu ₫"),
    )
    card_header("New vs Returning Revenue by Year", "Stacked · filtered period")
    st.plotly_chart(fig_nr, width="stretch", config=PLOT_CFG)
    card_close()


# ════════════════════════════════════ CASH FLOW ═══════════════════════════════
with tab_cashflow:
    bdf_raw = load_bookkeeping_df()

    if bdf_raw.empty:
        st.info("Không tải được dữ liệu từ sheet Bookkeeping.")
    else:
        # ── Filters ──────────────────────────────────────────────────────────
        cf_f1, cf_f2, cf_f3 = st.columns(3)
        cf_years = sorted(bdf_raw["year"].dropna().unique().astype(int).tolist(), reverse=True)
        cf_yr = cf_f1.selectbox("Năm", ["Tất cả"] + cf_years, key="cf_yr")
        cf_cats = sorted([c for c in bdf_raw["category"].dropna().unique() if c])
        cf_cat = cf_f2.selectbox("Category", ["Tất cả"] + cf_cats, key="cf_cat")
        cf_types = sorted([t for t in bdf_raw["cf_type"].dropna().unique() if t])
        cf_type = cf_f3.selectbox("Type", ["Tất cả"] + cf_types, key="cf_type")

        bdf = bdf_raw.copy()
        if cf_yr != "Tất cả":
            bdf = bdf[bdf["year"] == int(cf_yr)]
        if cf_cat != "Tất cả":
            bdf = bdf[bdf["category"] == cf_cat]
        if cf_type != "Tất cả":
            bdf = bdf[bdf["cf_type"] == cf_type]

        total_in  = bdf["cash_in"].sum()
        total_out = bdf["cash_out"].sum()
        net_cf    = total_in - total_out
        n_rows    = len(bdf)

        # ── KPI cards ────────────────────────────────────────────────────────
        ck1, ck2, ck3, ck4 = st.columns(4, gap="small")
        ck1.markdown(score_card_html("Cash In",       fmt_m(total_in),  pct_badge(None), f"{n_rows} dòng", C_BLUE,   icon="↓"), unsafe_allow_html=True)
        ck2.markdown(score_card_html("Cash Out",      fmt_m(total_out), pct_badge(None), f"{n_rows} dòng", C_ORANGE, icon="↑"), unsafe_allow_html=True)
        cf_col = C_GREEN if net_cf >= 0 else C_RED
        ck3.markdown(score_card_html("Net Cash Flow", fmt_m(net_cf),    pct_badge(None), "In − Out",       cf_col,   icon="⇄"), unsafe_allow_html=True)
        ck4.markdown(score_card_html("Transactions",  f"{n_rows:,}",    pct_badge(None), "dòng ghi nhận",  C_MUTED,  icon="#"), unsafe_allow_html=True)
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        # ── Monthly stacked bar ───────────────────────────────────────────────
        by_month = bdf.groupby("month_key")[["cash_in","cash_out"]].sum().reset_index().sort_values("month_key")
        by_month["net"] = by_month["cash_in"] - by_month["cash_out"]

        fig_bk = go.Figure()
        fig_bk.add_trace(go.Bar(
            x=by_month["month_key"], y=by_month["cash_in"] / 1e6,
            name="Cash In", marker_color=C_BLUE, marker_line_width=0,
            hovertemplate="<b>%{x}</b><br>Cash In: %{y:.0f}M ₫<extra></extra>",
        ))
        fig_bk.add_trace(go.Bar(
            x=by_month["month_key"], y=-by_month["cash_out"] / 1e6,
            name="Cash Out", marker_color=C_ORANGE, marker_line_width=0,
            hovertemplate="<b>%{x}</b><br>Cash Out: %{customdata:.0f}M ₫<extra></extra>",
            customdata=by_month["cash_out"] / 1e6,
        ))
        fig_bk.add_trace(go.Scatter(
            x=by_month["month_key"], y=by_month["net"] / 1e6,
            name="Net", mode="lines+markers",
            line=dict(color=C_GREEN if net_cf >= 0 else C_RED, width=2, dash="dot"),
            marker=dict(size=5),
            hovertemplate="<b>%{x}</b><br>Net: %{y:.0f}M ₫<extra></extra>",
        ))
        fig_bk.update_layout(
            **layout(), height=280, barmode="relative", bargap=0.25,
            xaxis=xax(tickangle=-30), yaxis=yax(title="triệu ₫"),
        )
        card_header("Monthly Cash Flow", "Cash In (xanh) · Cash Out (cam) · Net (đường)")
        st.plotly_chart(fig_bk, width="stretch", config=PLOT_CFG)
        card_close()

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # ── Category & Type breakdown ─────────────────────────────────────────
        cb1, cb2 = st.columns(2, gap="medium")
        with cb1:
            by_cat = (bdf.groupby("category")[["cash_in","cash_out"]]
                      .sum().reset_index()
                      .assign(net=lambda d: d["cash_in"] - d["cash_out"])
                      .sort_values("cash_out", ascending=False))
            fig_cat = go.Figure()
            fig_cat.add_trace(go.Bar(
                y=by_cat["category"], x=by_cat["cash_in"] / 1e6,
                name="Cash In", orientation="h", marker_color=C_BLUE, marker_line_width=0,
                hovertemplate="<b>%{y}</b><br>Cash In: %{x:.0f}M ₫<extra></extra>",
            ))
            fig_cat.add_trace(go.Bar(
                y=by_cat["category"], x=-by_cat["cash_out"] / 1e6,
                name="Cash Out", orientation="h", marker_color=C_ORANGE, marker_line_width=0,
                hovertemplate="<b>%{y}</b><br>Cash Out: %{customdata:.0f}M ₫<extra></extra>",
                customdata=by_cat["cash_out"] / 1e6,
            ))
            fig_cat.update_layout(
                **layout(), height=280, barmode="relative", bargap=0.3,
                xaxis=xax(title="triệu ₫"), yaxis=yax(),
            )
            card_header("By Category", "Cash In vs Cash Out")
            st.plotly_chart(fig_cat, width="stretch", config=PLOT_CFG)
            card_close()

        with cb2:
            by_type = (bdf.groupby("cf_type")[["cash_in","cash_out"]]
                       .sum().reset_index()
                       .assign(net=lambda d: d["cash_in"] - d["cash_out"])
                       .sort_values("cash_out", ascending=False))
            fig_type = go.Figure()
            fig_type.add_trace(go.Bar(
                y=by_type["cf_type"], x=by_type["cash_in"] / 1e6,
                name="Cash In", orientation="h", marker_color=C_BLUE, marker_line_width=0,
                hovertemplate="<b>%{y}</b><br>Cash In: %{x:.0f}M ₫<extra></extra>",
            ))
            fig_type.add_trace(go.Bar(
                y=by_type["cf_type"], x=-by_type["cash_out"] / 1e6,
                name="Cash Out", orientation="h", marker_color=C_ORANGE, marker_line_width=0,
                hovertemplate="<b>%{y}</b><br>Cash Out: %{customdata:.0f}M ₫<extra></extra>",
                customdata=by_type["cash_out"] / 1e6,
            ))
            fig_type.update_layout(
                **layout(), height=280, barmode="relative", bargap=0.3,
                xaxis=xax(title="triệu ₫"), yaxis=yax(),
            )
            card_header("By Type of Cash Flow", "Cash In vs Cash Out")
            st.plotly_chart(fig_type, width="stretch", config=PLOT_CFG)
            card_close()

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # ── Transaction table ─────────────────────────────────────────────────
        t_display = bdf[bdf["cash_in"].gt(0) | bdf["cash_out"].gt(0)].copy()
        t_display = t_display.sort_values("date", ascending=False).reset_index(drop=True)
        t_display["Cash In"]  = t_display["cash_in"].map(lambda x: f"{x:,.0f}" if x else "")
        t_display["Cash Out"] = t_display["cash_out"].map(lambda x: f"{x:,.0f}" if x else "")
        t_display["Net"]      = (t_display["cash_in"] - t_display["cash_out"]).map(lambda x: f"{x:,.0f}")
        t_out = t_display[["date","category","cf_type","description","Cash In","Cash Out","Net"]].copy()
        t_out["date"] = t_out["date"].dt.strftime("%d/%m/%Y").fillna("")
        t_out.columns = ["Date","Category","Type","Description","Cash In","Cash Out","Net"]

        st.caption(f"{len(t_out):,} giao dịch · Cash In {fmt_m(total_in)} · Cash Out {fmt_m(total_out)}")
        _bk_styled = t_out.style.set_properties(**{
            "background-color": C_SURFACE, "color": C_TEXT,
        }).set_table_styles([
            {"selector": "th", "props": [("background-color", C_SURFACE2), ("color", C_TEXT), ("border-bottom", f"1px solid {C_BORDER}")]},
            {"selector": "td", "props": [("border-bottom", f"1px solid {C_BORDER}")]},
        ])
        st.dataframe(_bk_styled, use_container_width=True, height=420, hide_index=True,
            column_config={
                "Date":        st.column_config.TextColumn("Date",        width="small"),
                "Category":    st.column_config.TextColumn("Category",    width="small"),
                "Type":        st.column_config.TextColumn("Type",        width="medium"),
                "Description": st.column_config.TextColumn("Description", width="large"),
                "Cash In":     st.column_config.TextColumn("Cash In",     width="medium"),
                "Cash Out":    st.column_config.TextColumn("Cash Out",    width="medium"),
                "Net":         st.column_config.TextColumn("Net",         width="medium"),
            })

# ════════════════════════════════════ CLIENTS ═════════════════════════════════
with tab_clients:

    col_c1, col_c2 = st.columns([3, 2], gap="medium")

    with col_c1:
        n = st.select_slider("Show top N clients", [10, 15, 20, 25, 30], value=15)
        top_c = (
            dff[dff["client"] != ""]
               .groupby("client")["net"].sum()
               .reset_index().sort_values("net", ascending=False).head(n)
        )
        top_c["M"]     = top_c["net"] / 1e6
        top_c["label"] = top_c["M"].map(lambda x: f"{x:.0f}M")
        bar_colors     = [C_BLUE if i < 3 else "rgba(20,83,248,0.42)" for i in range(len(top_c))]

        fig_cl = go.Figure(go.Bar(
            x=top_c["M"],
            y=top_c["client"],
            orientation="h",
            marker_color=bar_colors[::-1],
            marker_line_width=0,
            text=top_c["label"].values[::-1].tolist(),
            textposition="outside",
            textfont=dict(size=10, color=C_LABEL),
            hovertemplate="<b>%{y}</b><br>%{x:.0f}M ₫<extra></extra>",
        ))
        fig_cl.update_layout(**layout(
            height=max(300, n * 24),
            showlegend=False,
            margin=dict(t=8, b=8, l=4, r=60),
            xaxis=xax(title="Revenue (triệu ₫)"),
            yaxis=yax(autorange="reversed"),
        ))
        card_header(f"Top {n} Clients", "All-time · filtered period")
        st.plotly_chart(fig_cl, width="stretch", config=PLOT_CFG)
        card_close()

    with col_c2:
        # Concentration donut
        top5_rev = top_c.head(5)["net"].sum()
        rest_rev = dff["net"].sum() - top5_rev
        fig_conc = go.Figure(go.Pie(
            labels=list(top_c.head(5)["client"]) + ["Others"],
            values=list(top_c.head(5)["net"] / 1e6) + [rest_rev / 1e6],
            hole=0.6,
            marker=dict(
                colors=[C_BLUE, C_ORANGE, C_PURPLE, C_GREEN, C_YELLOW, C_MUTED],
                line=dict(color=C_SURFACE, width=2),
            ),
            textinfo="percent",
            textfont=dict(size=10, color=C_LABEL),
            hovertemplate="<b>%{label}</b><br>%{value:.0f}M · %{percent}<extra></extra>",
        ))
        fig_conc.update_layout(**layout(
            height=230, showlegend=True,
            legend=dict(font=dict(size=10), orientation="v",
                        x=1.02, y=0.5, xanchor="left"),
            margin=dict(t=8, b=8, l=0, r=100),
        ))
        card_header("Client Concentration", "Top 5 vs rest")
        st.plotly_chart(fig_conc, width="stretch", config=PLOT_CFG)
        card_close()

        # New clients per year
        new_yr = (
            dff[dff["new_client"] == "TRUE"]
               .groupby("year")["client"].nunique()
               .reset_index().sort_values("year")
        )
        fig_new = go.Figure(go.Bar(
            x=new_yr["year"].astype(str), y=new_yr["client"],
            marker_color=C_GREEN, marker_line_width=0, opacity=0.8,
            text=new_yr["client"], textposition="outside",
            textfont=dict(size=10, color=C_LABEL),
            hovertemplate="<b>%{x}</b><br>%{y} new clients<extra></extra>",
        ))
        fig_new.update_layout(
            **layout(), height=200, showlegend=False, bargap=0.35,
            xaxis=xax(type="category"),
            yaxis=yax(),
        )
        card_header("New / Reactivated Clients per Year")
        st.plotly_chart(fig_new, width="stretch", config=PLOT_CFG)
        card_close()

    # Client × Year heatmap
    top8 = (
        dff[dff["client"] != ""]
           .groupby("client")["net"].sum()
           .nlargest(8).index.tolist()
    )
    heat = (
        dff[dff["client"].isin(top8)]
           .groupby(["client", "year"])["net"].sum()
           .reset_index()
           .pivot(index="client", columns="year", values="net")
           .fillna(0) / 1e6
    )
    text_vals = [[f"{v:.0f}M" if v > 0 else "" for v in row] for row in heat.values]
    fig_heat  = go.Figure(go.Heatmap(
        z=heat.values,
        x=[str(c) for c in heat.columns],
        y=heat.index.tolist(),
        colorscale=[[0, C_SURFACE], [0.5, "rgba(20,83,248,0.5)"], [1, C_BLUE]],
        showscale=True,
        colorbar=dict(thickness=10, tickfont=dict(size=10, color=C_MUTED)),
        text=text_vals, texttemplate="%{text}", textfont=dict(size=10, color=C_LABEL),
        hovertemplate="<b>%{y}</b> · %{x}<br>%{z:.0f}M ₫<extra></extra>",
    ))
    fig_heat.update_layout(**layout(
        height=260,
        margin=dict(t=8, b=8, l=120, r=8),
        xaxis=xax(),
        yaxis=yax(autorange="reversed"),
    ))
    card_header("Top 8 Clients · Revenue by Year", "Heatmap — deeper blue = higher revenue")
    st.plotly_chart(fig_heat, width="stretch", config=PLOT_CFG)
    card_close()


# ════════════════════════════════ PRODUCTS & REPS ════════════════════════════
with tab_products:

    pc1, pc2 = st.columns(2, gap="medium")

    with pc1:
        by_prod = (
            dff[dff["product"] != ""]
               .groupby("product")["net"].sum()
               .reset_index().sort_values("net", ascending=False)
        )
        by_prod = by_prod[by_prod["net"] > 0]
        fig_prod = go.Figure(go.Pie(
            labels=by_prod["product"],
            values=by_prod["net"] / 1e6,
            hole=0.55,
            marker=dict(colors=PALETTE, line=dict(color=C_SURFACE, width=2)),
            textinfo="label+percent",
            textposition="outside",
            textfont=dict(size=10, color=C_LABEL),
            hovertemplate="<b>%{label}</b><br>%{value:.0f}M · %{percent}<extra></extra>",
        ))
        fig_prod.update_layout(**layout(
            height=300, showlegend=False,
            margin=dict(t=8, b=8, l=0, r=0),
        ))
        card_header("Product / Service Mix", "Share of total revenue")
        st.plotly_chart(fig_prod, width="stretch", config=PLOT_CFG)
        card_close()

    with pc2:
        by_type = (
            dff[dff["project_type"] != ""]
               .groupby("project_type")["net"].sum()
               .reset_index().sort_values("net", ascending=False)
        )
        by_type["M"]     = by_type["net"] / 1e6
        by_type["label"] = by_type["M"].map(lambda x: f"{x:.0f}M")
        fig_type = go.Figure(go.Bar(
            x=by_type["project_type"], y=by_type["M"],
            marker_color=PALETTE[:len(by_type)], marker_line_width=0,
            text=by_type["label"], textposition="outside",
            textfont=dict(size=10, color=C_LABEL),
            hovertemplate="<b>%{x}</b><br>%{y:.0f}M ₫<extra></extra>",
        ))
        fig_type.update_layout(
            **layout(), height=300, showlegend=False, bargap=0.4,
            xaxis=xax(),
            yaxis=yax(),
        )
        card_header("Revenue by Project Type")
        st.plotly_chart(fig_type, width="stretch", config=PLOT_CFG)
        card_close()

    # Stacked area — product trend
    top_prods = (
        dff[dff["product"] != ""]
           .groupby("product")["net"].sum()
           .nlargest(5).index.tolist()
    )
    prod_trend = (
        dff[dff["product"].isin(top_prods)]
           .groupby(["year", "product"])["net"].sum()
           .reset_index()
    )
    fig_stack = go.Figure()
    for i, prod in enumerate(top_prods):
        yd = prod_trend[prod_trend["product"] == prod].sort_values("year")
        fig_stack.add_trace(go.Scatter(
            x=yd["year"].astype(str), y=yd["net"] / 1e6,
            name=prod, stackgroup="one",
            line=dict(color=PALETTE[i], width=0.5),
            hovertemplate=f"<b>{prod}</b><br>%{{y:.0f}}M ₫<extra></extra>",
        ))
    fig_stack.update_layout(
        **layout(), height=250,
        xaxis=xax(type="category"),
        yaxis=yax(title="triệu ₫"),
    )
    card_header("Product Revenue Stack by Year", "Top 5 products")
    st.plotly_chart(fig_stack, width="stretch", config=PLOT_CFG)
    card_close()

    # Sales rep
    by_rep = (
        dff[dff["sales_rep"] != ""]
           .groupby("sales_rep")["net"].sum()
           .reset_index().sort_values("net", ascending=False)
    )
    by_rep["M"]     = by_rep["net"] / 1e6
    by_rep["deals"] = (
        dff[dff["sales_rep"] != ""]
           .groupby("sales_rep")["net"].count()
           .reindex(by_rep["sales_rep"]).values
    )
    by_rep["avg"]   = by_rep["M"] / by_rep["deals"].clip(lower=1)
    by_rep["label"] = by_rep["M"].map(lambda x: f"{x:.0f}M")

    rc1, rc2 = st.columns(2, gap="medium")
    with rc1:
        fig_rep = go.Figure(go.Bar(
            x=by_rep["sales_rep"], y=by_rep["M"],
            marker_color=C_ORANGE, marker_line_width=0, opacity=0.85,
            text=by_rep["label"], textposition="outside",
            textfont=dict(size=11, color=C_LABEL),
            hovertemplate="<b>%{x}</b><br>%{y:.0f}M ₫<extra></extra>",
        ))
        fig_rep.update_layout(
            **layout(), height=230, showlegend=False, bargap=0.4,
            xaxis=xax(),
            yaxis=yax(),
        )
        card_header("Revenue by Sales Rep")
        st.plotly_chart(fig_rep, width="stretch", config=PLOT_CFG)
        card_close()

    with rc2:
        fig_avg = go.Figure(go.Bar(
            x=by_rep["sales_rep"],
            y=by_rep["avg"],
            marker_color=C_PURPLE, marker_line_width=0, opacity=0.85,
            text=by_rep["avg"].map(lambda x: f"{x:.0f}M"),
            textposition="outside", textfont=dict(size=11, color=C_LABEL),
            hovertemplate="<b>%{x}</b><br>Avg: %{y:.0f}M ₫<extra></extra>",
        ))
        fig_avg.update_layout(
            **layout(), height=230, showlegend=False, bargap=0.4,
            xaxis=xax(),
            yaxis=yax(),
        )
        card_header("Avg Deal Size by Sales Rep")
        st.plotly_chart(fig_avg, width="stretch", config=PLOT_CFG)
        card_close()


# ════════════════════════════════ TRANSACTIONS ════════════════════════════════
with tab_data:
    sc1, sc2, sc3 = st.columns(3)
    search  = sc1.text_input("Search project / client", placeholder="Type to filter...")
    yr_fil  = sc2.selectbox("Year", ["All"] + sorted(dff["year"].dropna().unique().astype(int).tolist(), reverse=True))
    rep_fil = sc3.selectbox("Sales Rep", ["All"] + sorted([r for r in dff["sales_rep"].unique() if r]))

    tdf = dff.copy()
    if search:
        mask = (
            tdf["name"].str.contains(search, case=False, na=False) |
            tdf["client"].str.contains(search, case=False, na=False)
        )
        tdf = tdf[mask]
    if yr_fil != "All":
        tdf = tdf[tdf["year"] == int(yr_fil)]
    if rep_fil != "All":
        tdf = tdf[tdf["sales_rep"] == rep_fil]

    st.caption(f"{len(tdf)} transactions · {fmt_b(tdf['net'].sum())}")

    display = tdf[["date_str","name","client","product","project_type","sales_rep","net_raw","net"]].copy()
    display.columns = ["Date","Project","Client","Product","Type","Sales Rep","Revenue (raw)","Revenue (₫)"]
    display = display.sort_values("Date", ascending=False).reset_index(drop=True)
    display["Revenue (₫)"] = display["Revenue (₫)"].map(lambda x: f"{x:,.0f}")

    _styled = display.style.set_properties(**{
        "background-color": C_SURFACE,
        "color": C_TEXT,
    }).set_table_styles([
        {"selector": "th", "props": [
            ("background-color", C_SURFACE2),
            ("color", C_TEXT),
            ("border-bottom", f"1px solid {C_BORDER}"),
        ]},
        {"selector": "td", "props": [
            ("border-bottom", f"1px solid {C_BORDER}"),
        ]},
    ])

    st.dataframe(
        _styled, use_container_width=True, height=520, hide_index=True,
        column_config={
            "Date":          st.column_config.TextColumn("Date",    width="small"),
            "Project":       st.column_config.TextColumn("Project", width="large"),
            "Client":        st.column_config.TextColumn("Client",  width="medium"),
            "Revenue (₫)":   st.column_config.TextColumn("Revenue", width="medium"),
        },
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div style="margin-top:28px;padding:14px 20px;border-top:1px solid {C_BORDER};'
    f'display:flex;justify-content:space-between;align-items:center">'
    f'<div style="display:flex;align-items:center;gap:8px">'
    f'<div style="width:18px;height:18px;background:{C_BLUE};border-radius:4px;'
    f'display:flex;align-items:center;justify-content:center;font-size:9px;'
    f'font-weight:800;color:#FCF6EE">F</div>'
    f'<span style="font-size:11px;color:{C_MUTED}">Fillinus · Revenue Dashboard · '
    f'<span style="color:{C_BLUE}">Google Sheets</span> · ~60s refresh</span>'
    f'</div>'
    f'<span style="font-size:11px;color:{C_MUTED}">'
    f'{len(dff)} rows · {last_loaded}</span>'
    f'</div>',
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════════════════════════
# FLOATING AI CHAT WIDGET
# ══════════════════════════════════════════════════════════════════════════════
if "chat_open" not in st.session_state:
    st.session_state["chat_open"] = False
if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = []

_fab_client = _get_groq_client()
_fab_has_key = _fab_client is not None

_fab_container = st.container()
with _fab_container:
    if st.session_state["chat_open"]:
        # ── Panel header ──────────────────────────────────────────────────────
        _hc1, _hc2 = st.columns([5, 2])
        with _hc1:
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;padding:12px 4px 8px">'
                f'<div style="width:28px;height:28px;background:{C_BLUE};border-radius:7px;'
                f'display:flex;align-items:center;justify-content:center;'
                f'font-size:12px;font-weight:800;color:#FCF6EE;flex-shrink:0">F</div>'
                f'<div>'
                f'<div style="font-size:13px;font-weight:700;color:{C_TEXT};line-height:1.1">'
                f'Fillinus AI</div>'
                f'<div style="font-size:10px;color:{C_MUTED}">Analyst · Strategist · Growth · Talent</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        with _hc2:
            _hb1, _hb2 = st.columns(2)
            with _hb1:
                _can_clear = bool(st.session_state["chat_messages"])
                if st.button("↺", key="fab_clear", use_container_width=True,
                             help="Clear chat", disabled=not _can_clear):
                    st.session_state["chat_messages"] = []
                    st.rerun()
            with _hb2:
                if st.button("✕", key="fab_close", use_container_width=True):
                    st.session_state["chat_open"] = False
                    st.rerun()

        st.markdown(
            f'<div style="height:1px;background:{C_BORDER};margin:0 0 8px"></div>',
            unsafe_allow_html=True,
        )

        # ── No API key warning ────────────────────────────────────────────────
        if not _fab_has_key:
            st.markdown(
                f'<div style="padding:12px;background:rgba(239,68,68,0.08);'
                f'border:1px solid rgba(239,68,68,0.2);border-radius:8px;'
                f'font-size:12px;color:{C_MUTED}">'
                f'⚠️ Chưa cấu hình <code>groq_api_key</code> trong Streamlit Secrets.</div>',
                unsafe_allow_html=True,
            )
        else:
            # ── Message history ───────────────────────────────────────────────
            _msg_area = st.container(height=320, border=False)
            with _msg_area:
                if not st.session_state["chat_messages"]:
                    st.markdown(
                        f'<div style="text-align:center;padding:40px 12px;color:{C_MUTED};'
                        f'font-size:12px;line-height:1.8">'
                        f'💬<br>Hỏi về doanh thu, chiến lược<br>marketing hoặc artist</div>',
                        unsafe_allow_html=True,
                    )
                for _m in st.session_state["chat_messages"]:
                    with st.chat_message(_m["role"]):
                        st.markdown(_m["content"])

            # ── Generate assistant reply if last msg is from user ─────────────
            _fab_msgs = st.session_state["chat_messages"]
            if _fab_msgs and _fab_msgs[-1]["role"] == "user":
                with st.spinner("Đang xử lý..."):
                    _dc = _build_data_context(df)
                    _sp = _chat_system_prompt(_dc)
                    _api_m = [{"role": x["role"], "content": x["content"]} for x in _fab_msgs]
                    try:
                        _reply = "".join(_stream_chat(_fab_client, _api_m, _sp))
                    except Exception as _ex:
                        _es = str(_ex).lower()
                        if "rate_limit" in _es or "429" in _es or "quota" in _es:
                            _reply = (
                                "⚠️ **Đã vượt rate limit Groq API.**\n\n"
                                "Free tier: 14,400 req/ngày. "
                                "Vào **console.groq.com** để kiểm tra usage."
                            )
                        else:
                            _reply = f"⚠️ Lỗi API: {_ex}"
                st.session_state["chat_messages"].append({"role": "assistant", "content": _reply})
                st.rerun()

            # ── Input form ────────────────────────────────────────────────────
            with st.form("fab_chat_form", clear_on_submit=True, border=False):
                _fi_cols = st.columns([7, 1])
                with _fi_cols[0]:
                    _fab_input = st.text_input(
                        "", placeholder="Nhập câu hỏi...",
                        label_visibility="collapsed",
                    )
                with _fi_cols[1]:
                    _fab_send = st.form_submit_button("→", use_container_width=True)

            if _fab_send and _fab_input:
                st.session_state["chat_messages"].append({"role": "user", "content": _fab_input})
                st.rerun()

    # ── FAB toggle button ─────────────────────────────────────────────────────
    _fab_icon = "✕" if st.session_state["chat_open"] else "💬"
    if st.button(_fab_icon, key="fab_toggle", type="primary", use_container_width=False):
        st.session_state["chat_open"] = not st.session_state["chat_open"]
        st.rerun()

# Float the container to bottom-right
_fab_w = "380px" if st.session_state["chat_open"] else "auto"
_fab_container.float(
    f"bottom: 24px; right: 24px; z-index: 9999; width: {_fab_w}; "
    f"background: {C_SURFACE}; border: 1px solid {C_BORDER}; "
    f"border-radius: 16px; padding: 0 12px 12px; "
    f"box-shadow: 0 8px 32px rgba(0,0,0,0.35);"
)
