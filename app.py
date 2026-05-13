import streamlit as st
import json
import os
import io

from datetime import date, datetime, timedelta
import calendar
import pandas as pd
from fpdf import FPDF

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Shift Roster App",
    page_icon="🕐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Duty meta ─────────────────────────────────────────────────────────────────
DUTY_TYPES = {
    "M":  {"label": "M",  "full": "Morning Shift",  "time": "07:00 – 14:00", "color": "#f59e0b", "bg": "rgba(245,158,11,0.15)"},
    "E":  {"label": "E",  "full": "Evening Shift",  "time": "14:00 – 22:00", "color": "#8b5cf6", "bg": "rgba(139,92,246,0.15)"},
    "N":  {"label": "N",  "full": "Night Shift",    "time": "22:00 – 07:00", "color": "#0ea5e9", "bg": "rgba(14,165,233,0.15)"},
    "R":  {"label": "R",  "full": "Rest Day",       "time": "All Day",       "color": "#64748b", "bg": "rgba(100,116,139,0.15)"},
    "RT": {"label": "RT", "full": "Retraining",     "time": "08:00 – 16:00", "color": "#10b981", "bg": "rgba(16,185,129,0.15)"},
    "G":  {"label": "G",  "full": "General Shift",  "time": "08:00 – 16:00", "color": "#f97316", "bg": "rgba(249,115,22,0.15)"},
    "NA": {"label": "–",  "full": "Super Week",     "time": "All Day",       "color": "#475569", "bg": "rgba(71,85,105,0.1)"},
}
CREWS = [1, 2, 3, 4, 5, 6]

# ── Load roster data ───────────────────────────────────────────────────────────
@st.cache_data
def load_roster():
    # Try multiple path strategies for local + Streamlit Cloud compatibility
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "roster_data.json"),
        os.path.join(os.getcwd(), "roster_data.json"),
        "roster_data.json",
    ]
    for p in candidates:
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(f"roster_data.json not found. Searched: {candidates}")

def get_duty(roster, crew_id, target_date):
    key = target_date.strftime("%Y-%m-%d")
    day_data = roster.get(key, {})
    code = day_data.get(str(crew_id), "NA")
    if code == "NA" or code == "\u2013" or code == "-":
        return DUTY_TYPES["NA"]
    return DUTY_TYPES.get(code, {"label": code, "full": "Unknown", "time": "\u2013", "color": "#94a3b8", "bg": "rgba(148,163,184,0.1)"})

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ─── Global ─── */
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #0f172a; color: #e2e8f0; }
.block-container { padding: 1.5rem 2rem !important; max-width: 1400px; }
section[data-testid="stSidebar"] { display:none; }

/* ─── Hide Streamlit chrome ─── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display:none; }

/* ─── Cards ─── */
.card {
    background: linear-gradient(135deg, #1e293b 0%, #162032 100%);
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 16px;
}
.card-sm { padding: 16px; border-radius: 12px; }

/* ─── Page title ─── */
.page-header {
    display: flex; align-items: center; gap: 14px;
    margin-bottom: 28px; padding-bottom: 20px;
    border-bottom: 1px solid #1e293b;
}
.page-title { font-size: 1.6rem; font-weight: 800; color: #f1f5f9; margin:0; }
.page-sub   { font-size: 0.85rem; color: #64748b; margin:0; }

/* ─── Status card ─── */
.status-card {
    background: linear-gradient(135deg, #1e293b, #0f1f35);
    border-radius: 20px; padding: 32px 24px;
    text-align: center; border: 1px solid #334155;
    box-shadow: 0 20px 40px rgba(0,0,0,0.4);
}
.status-date { font-size:0.78rem; color:#64748b; text-transform:uppercase; letter-spacing:2px; margin-bottom:8px; }
.status-big  { font-size:2.8rem; font-weight:800; margin:8px 0 4px; line-height:1; }
.status-name { font-size:1.1rem; color:#94a3b8; margin:0 0 6px; }
.status-time { font-size:0.85rem; color:#475569; }

/* ─── Crew badge ─── */
.crew-badge {
    display:inline-block; padding:4px 14px; border-radius:20px;
    background:rgba(59,130,246,0.15); border:1px solid rgba(59,130,246,0.3);
    color:#60a5fa; font-size:0.78rem; font-weight:700; letter-spacing:1px;
}

/* ─── Greeting ─── */
.greeting { font-size:1.25rem; font-weight:700; color:#f1f5f9; }

/* ─── Roster table ─── */
.roster-wrap { overflow-x:auto; border-radius:14px; border:1px solid #1e293b; }
.roster-table {
    border-collapse:collapse; width:100%;
    font-size:0.78rem; white-space:nowrap;
}
.roster-table th {
    background:#1e293b; color:#64748b; font-weight:bold;
    padding:10px 8px; text-align:center;
    border-bottom:1px solid #334155; border-right:1px solid #1a2540;
    position:sticky; top:0; z-index:10;
}
.roster-table td {
    padding:9px 6px; text-align:center;
    border-bottom:1px solid #1a2540; border-right:1px solid #1a2540;
}
.roster-table .crew-col {
    position:sticky; left:0; background:#0f172a; z-index:5;
    font-weight:700; color:#3b82f6; min-width:72px;
    border-right:2px solid #334155 !important;
}
.roster-table .crew-col.mine { background:#1d4ed8; color:#fff; }
.roster-table .today-hdr { background:rgba(59,130,246,0.2) !important; color:#93c5fd !important; border-bottom:2px solid #3b82f6 !important; }
.roster-table .today-col { background:rgba(59,130,246,0.05); }
.roster-table .today-mine { outline:2px solid #3b82f6; outline-offset:-2px; }
.me-tag { font-size:0.55rem; display:block; color:rgba(255,255,255,0.6); }

/* duty colours */
.d-M  { color:#f59e0b; font-weight:700; }
.d-E  { color:#8b5cf6; font-weight:700; }
.d-N  { color:#0ea5e9; font-weight:700; }
.d-R  { color:#475569; }
.d-RT { color:#10b981; font-weight:700; }
.d-G  { color:#f97316; font-weight:700; }
.d-   { color:#334155; }

/* ─── Legend ─── */
.legend { display:flex; flex-wrap:wrap; gap:14px; margin-bottom:14px; }
.l-item { display:flex; align-items:center; gap:6px; font-size:0.75rem; color:#94a3b8; }
.l-dot  { width:9px; height:9px; border-radius:50%; flex-shrink:0; }

/* ─── Login page ─── */
.login-wrap { max-width:420px; margin:10vh auto 0; }
.login-title { font-size:2rem; font-weight:800; color:#f1f5f9; text-align:center; margin-bottom:6px; }
.login-sub   { text-align:center; color:#64748b; margin-bottom:28px; font-size:0.9rem; }

/* ─── Crew selector ─── */
.crew-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin:10px 0 20px; }
.crew-btn {
    background:#1e293b; border:1px solid #334155;
    border-radius:10px; padding:14px 8px; text-align:center;
    cursor:pointer; transition:all 0.2s; color:#94a3b8; font-weight:600;
    font-size:0.9rem;
}
.crew-btn:hover   { border-color:#3b82f6; color:#60a5fa; }
.crew-btn.selected { border-color:#3b82f6; background:rgba(59,130,246,0.15); color:#60a5fa; }

/* ─── Buttons ─── */
.stButton > button {
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    color: white; border: none; border-radius: 10px;
    padding: 12px 24px; font-weight: 600; font-size: 0.95rem;
    cursor: pointer; transition: all 0.2s; width: 100%;
    box-shadow: 0 4px 15px rgba(37,99,235,0.3);
}
.stButton > button:hover { transform:translateY(-1px); box-shadow:0 6px 20px rgba(37,99,235,0.45); }

/* ─── Inputs ─── */
.stTextInput > div > div > input {
    background:#1e293b !important; border:1px solid #334155 !important;
    color:#f1f5f9 !important; border-radius:10px !important; padding:12px !important;
}
.stTextInput > div > div > input:focus { border-color:#3b82f6 !important; }
.stTextInput label { color:#94a3b8 !important; font-size:0.85rem !important; font-weight:500 !important; }

/* selectbox */
.stSelectbox > div > div { background:#1e293b !important; border:1px solid #334155 !important; border-radius:10px !important; color:#f1f5f9 !important; }
.stSelectbox label { color:#94a3b8 !important; font-size:0.85rem !important; font-weight:500 !important; }

/* ─── Month nav ─── */
.month-pill {
    display:inline-flex; align-items:center; gap:8px;
    background:#1e293b; border:1px solid #334155;
    border-radius:20px; padding:6px 16px; font-weight:700; color:#f1f5f9;
}
.nav-btn {
    background:#1e293b; border:1px solid #334155; border-radius:8px;
    color:#94a3b8; padding:6px 14px; cursor:pointer; font-size:1.1rem;
    transition:all 0.2s;
}
.nav-btn:hover { background:#334155; color:#f1f5f9; }

/* ─── Top bar ─── */
.top-bar {
    display:flex; justify-content:space-between; align-items:center;
    margin-bottom:24px; padding-bottom:16px; border-bottom:1px solid #1e293b;
}
.stAlert { border-radius:10px; }

/* ─── Landscape Reminder ─── */
@media screen and (orientation: portrait) and (max-width: 768px) {
    body::before {
        content: "🔄 Please rotate your device to Landscape mode for the best view";
        position: fixed; top: 0; left: 0; width: 100%;
        background: #2563eb; color: white;
        text-align: center; padding: 10px; font-size: 0.8rem;
        font-weight: 700; z-index: 9999;
    }
}
</style>
<link rel="manifest" href="manifest.json">
""", unsafe_allow_html=True)

# ── Timezone Adjustment (UTC+5 for local time accuracy) ────────────────────────
def get_local_today():
    from datetime import timezone
    # Adjust hours=5 for your local timezone (e.g., Pakistan +5)
    return datetime.now(timezone(timedelta(hours=5))).date()

today = get_local_today()

# ── Session state defaults ─────────────────────────────────────────────────────
if "logged_in"   not in st.session_state: st.session_state.logged_in   = False
if "username"    not in st.session_state: st.session_state.username     = ""
if "crew_id"     not in st.session_state: st.session_state.crew_id      = None
if "view_year"   not in st.session_state: st.session_state.view_year    = today.year
if "view_month"  not in st.session_state: st.session_state.view_month   = today.month

# ── Auto-login from URL query params (remembers across sessions) ──────────────
if not st.session_state.logged_in:
    params = st.query_params
    saved_user = params.get("user", "")
    saved_crew = params.get("crew", "")
    if saved_user and saved_crew:
        try:
            st.session_state.logged_in = True
            st.session_state.username  = saved_user
            st.session_state.crew_id   = int(saved_crew)
        except ValueError:
            pass

roster = load_roster()

# ══════════════════════════════════════════════════════════════════════════════
#  LOGIN PAGE
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    st.markdown("""
    <div class='login-wrap'>
      <div style='text-align:center;font-size:3rem;margin-bottom:8px;'>🕐</div>
      <h1 class='login-title'>Shift Roster</h1>
      <p class='login-sub'>Enter your details to view your schedule</p>
    </div>
    """, unsafe_allow_html=True)

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown("<div class='card'>", unsafe_allow_html=True)

        name = st.text_input("Your Name", placeholder="Enter your name…", key="login_name")

        st.markdown("<p style='color:#94a3b8;font-size:0.85rem;font-weight:500;margin:16px 0 8px;'>Select Your Crew</p>", unsafe_allow_html=True)
        crew_sel = st.selectbox("", options=["— Choose crew —"] + [f"Crew {c}" for c in CREWS],
                                 label_visibility="collapsed", key="crew_select")

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("🔓  Enter Dashboard", use_container_width=True):
            if not name.strip():
                st.error("Please enter your name.")
            elif crew_sel == "— Choose crew —":
                st.error("Please select a crew.")
            else:
                crew_num = int(crew_sel.split()[-1])
                st.session_state.logged_in  = True
                st.session_state.username   = name.strip()
                st.session_state.crew_id    = crew_num
                st.query_params["user"] = name.strip()
                st.query_params["crew"] = str(crew_num)
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
today      = get_local_today()
crew_id    = st.session_state.crew_id
username   = st.session_state.username
today_duty = get_duty(roster, crew_id, today)

# ── Top bar ───────────────────────────────────────────────────────────────────
col_a, col_b = st.columns([6, 1])
with col_a:
    st.markdown(f"""
    <div class='top-bar'>
      <div>
        <div class='greeting'>👋 Welcome, {username}</div>
        <div style='color:#475569;font-size:0.82rem;margin-top:2px;'>
          {today.strftime('%A, %d %B %Y')}
        </div>
      </div>
      <span class='crew-badge'>CREW {crew_id}</span>
    </div>
    """, unsafe_allow_html=True)
with col_b:
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.username  = ""
        st.session_state.crew_id   = None
        st.query_params.clear()
        st.rerun()

# ── Row 1: Today status + upcoming ───────────────────────────────────────────
col1, col2, col3 = st.columns([1.4, 1, 1])

with col1:
    st.markdown(f"""
    <div class='status-card'>
      <div class='status-date'>{today.strftime('%A').upper()} &nbsp;·&nbsp; TODAY</div>
      <div class='status-big' style='color:{today_duty["color"]};'>{today_duty["label"]}</div>
      <div class='status-name'>{today_duty["full"]}</div>
      <div class='status-time'>⏰ {today_duty["time"]}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    # Next 7 days preview
    st.markdown("<div class='card card-sm'>", unsafe_allow_html=True)
    st.markdown("<p style='color:#64748b;font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;'>Next 7 Days</p>", unsafe_allow_html=True)
    for i in range(1, 8):
        d = today + timedelta(days=i)
        du = get_duty(roster, crew_id, d)
        st.markdown(f"""
        <div style='display:flex;justify-content:space-between;align-items:center;
             padding:6px 0;border-bottom:1px solid #1e293b;'>
          <span style='color:#64748b;font-size:0.78rem;'>{d.strftime('%a %d')}</span>
          <span style='color:{du["color"]};font-size:0.78rem;font-weight:700;'>{du["label"]}</span>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with col3:
    # Monthly shift summary
    st.markdown("<div class='card card-sm'>", unsafe_allow_html=True)
    st.markdown("<p style='color:#64748b;font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;'>This Month Summary</p>", unsafe_allow_html=True)
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    counts = {"M": 0, "E": 0, "N": 0, "R": 0, "RT": 0, "G": 0, "\u2013": 0}
    for dd in range(1, days_in_month + 1):
        du = get_duty(roster, crew_id, date(today.year, today.month, dd))
        if du["label"] in counts:
            counts[du["label"]] += 1
    label_map = {"M": "Morning", "E": "Evening", "N": "Night", "R": "Rest", "RT": "Retrain", "G": "General", "\u2013": "Super Week"}
    for code, cnt in counts.items():
        if cnt > 0:
            if code == "\u2013":
                meta = DUTY_TYPES["NA"]
            else:
                meta = DUTY_TYPES[code]
            st.markdown(f"""
            <div style='display:flex;justify-content:space-between;align-items:center;
                 padding:6px 0;border-bottom:1px solid #1e293b;'>
              <span style='color:{meta["color"]};font-size:0.78rem;font-weight:600;'>{label_map[code]}</span>
              <span style='background:{meta["bg"]};color:{meta["color"]};border-radius:20px;
                   padding:2px 10px;font-size:0.75rem;font-weight:700;'>{cnt} days</span>
            </div>
            """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Roster table section ──────────────────────────────────────────────────────
# Month navigation
nav_l, nav_mid, nav_r, nav_space = st.columns([1, 2, 1, 3])
with nav_l:
    can_go_prev = not (st.session_state.view_year == 2026 and st.session_state.view_month == 1)
    if st.button("◀  Prev", disabled=not can_go_prev):
        m = st.session_state.view_month - 1
        y = st.session_state.view_year
        if m < 1:
            m = 12; y -= 1
        st.session_state.view_month = m
        st.session_state.view_year  = y
        st.rerun()
with nav_mid:
    vy = st.session_state.view_year
    vm = st.session_state.view_month
    st.markdown(f"""
    <div style='text-align:center;'>
      <span class='month-pill'>📅 {calendar.month_name[vm]} {vy}</span>
    </div>
    """, unsafe_allow_html=True)
with nav_r:
    can_go_next = not (st.session_state.view_year == 2030 and st.session_state.view_month == 12)
    if st.button("Next  ▶", disabled=not can_go_next):
        m = st.session_state.view_month + 1
        y = st.session_state.view_year
        if m > 12:
            m = 1; y += 1
        st.session_state.view_month = m
        st.session_state.view_year  = y
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# Legend
st.markdown("""
<div class='legend'>
  <div class='l-item'><div class='l-dot' style='background:#f59e0b;'></div>M – Morning (07-14)</div>
  <div class='l-item'><div class='l-dot' style='background:#8b5cf6;'></div>E – Evening (14-22)</div>
  <div class='l-item'><div class='l-dot' style='background:#0ea5e9;'></div>N – Night (22-07)</div>
  <div class='l-item'><div class='l-dot' style='background:#64748b;'></div>R – Rest</div>
  <div class='l-item'><div class='l-dot' style='background:#10b981;'></div>RT – Retraining</div>
  <div class='l-item'><div class='l-dot' style='background:#f97316;'></div>G – General (08-16)</div>
</div>
""", unsafe_allow_html=True)

# Build table
vy = st.session_state.view_year
vm = st.session_state.view_month
days_in_month = calendar.monthrange(vy, vm)[1]
is_current_month = (vy == today.year and vm == today.month)
day_abbr = ["Su","Mo","Tu","We","Th","Fr","Sa"]

# Header rows
date_headers = ""
day_headers  = ""
for dd in range(1, days_in_month + 1):
    d_obj  = date(vy, vm, dd)
    is_tod = is_current_month and dd == today.day
    cls    = " class='today-hdr'" if is_tod else ""
    date_headers += f"<th{cls}>{dd}</th>"
    day_headers  += f"<th{cls}>{day_abbr[d_obj.weekday() % 7 if False else d_obj.isoweekday() % 7]}</th>"

# Body rows
body_rows = ""
for cr in CREWS:
    is_mine = (cr == crew_id)
    crew_cls = "crew-col mine" if is_mine else "crew-col"
    you_tag  = "<span class='me-tag'>YOU</span>" if is_mine else ""
    row = f"<tr><td class='{crew_cls}'>Crew {cr}{you_tag}</td>"
    for dd in range(1, days_in_month + 1):
        d_obj  = date(vy, vm, dd)
        du     = get_duty(roster, cr, d_obj)
        is_tod = is_current_month and dd == today.day
        lbl    = du["label"]
        color  = du["color"]
        td_cls = ""
        if is_tod:
            td_cls = "today-mine" if is_mine else "today-col"
        row += f"<td class='{td_cls}' style='color:{color};font-weight:600;'>{lbl}</td>"
    row += "</tr>"
    body_rows += row

html_table = f"""
<div class='roster-wrap'>
  <table class='roster-table'>
    <thead>
      <tr><th class='crew-col' style='position:sticky;left:0;top:0;z-index:30;background:#0f172a;'>Crew</th>{date_headers}</tr>
      <tr><th class='crew-col' style='position:sticky;left:0;top:41px;z-index:29;background:#0f172a;'>Day</th>{day_headers}</tr>
    </thead>
    <tbody>{body_rows}</tbody>
  </table>
</div>
"""
st.markdown(html_table, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── PDF Download Section ──────────────────────────────────────────────────────
def generate_roster_pdf(roster, crew_id, start_year, start_month, num_months=3):
    """Generate a styled PDF roster for the given months."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)

    # Color mapping for duty codes (RGB)
    duty_colors = {
        "M":  (245, 158, 11),
        "E":  (139, 92, 246),
        "N":  (14, 165, 233),
        "R":  (100, 116, 139),
        "RT": (16, 185, 129),
        "G":  (249, 115, 22),
        "\u2013":  (71, 85, 105),
    }

    y_cur = start_year
    m_cur = start_month

    for _ in range(num_months):
        pdf.add_page()
        month_name = calendar.month_name[m_cur]
        dim = calendar.monthrange(y_cur, m_cur)[1]

        # Title
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 12, f"Shift Roster  -  {month_name} {y_cur}", ln=True, align="C")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 6, f"Crew {crew_id} highlighted  |  Generated {datetime.now().strftime('%d %b %Y %H:%M')}", ln=True, align="C")
        pdf.ln(4)

        # Table dimensions
        crew_col_w = 20
        avail_w = pdf.w - pdf.l_margin - pdf.r_margin - crew_col_w
        day_col_w = avail_w / dim
        row_h = 8

        day_abbr_pdf = ["Su","Mo","Tu","We","Th","Fr","Sa"]

        # Header row 1: dates
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_fill_color(30, 41, 59)
        pdf.set_text_color(200, 200, 210)
        pdf.cell(crew_col_w, row_h, "Crew", border=1, fill=True, align="C")
        for dd in range(1, dim + 1):
            pdf.cell(day_col_w, row_h, str(dd), border=1, fill=True, align="C")
        pdf.ln()

        # Header row 2: day names
        pdf.cell(crew_col_w, row_h, "Day", border=1, fill=True, align="C")
        for dd in range(1, dim + 1):
            d_obj = date(y_cur, m_cur, dd)
            dn = day_abbr_pdf[d_obj.isoweekday() % 7]
            pdf.cell(day_col_w, row_h, dn, border=1, fill=True, align="C")
        pdf.ln()

        # Data rows
        for cr in CREWS:
            is_mine = (cr == crew_id)
            if is_mine:
                pdf.set_fill_color(29, 78, 216)
                pdf.set_text_color(255, 255, 255)
            else:
                pdf.set_fill_color(241, 245, 249)
                pdf.set_text_color(30, 41, 59)

            pdf.set_font("Helvetica", "B", 7)
            label_txt = f"Crew {cr}"
            if is_mine:
                label_txt += " *"
            pdf.cell(crew_col_w, row_h, label_txt, border=1, fill=True, align="C")

            for dd in range(1, dim + 1):
                d_obj = date(y_cur, m_cur, dd)
                du = get_duty(roster, cr, d_obj)
                lbl = du["label"]
                rgb = duty_colors.get(lbl, (148, 163, 184))

                if is_mine:
                    pdf.set_fill_color(29, 58, 150)
                else:
                    pdf.set_fill_color(255, 255, 255)

                pdf.set_text_color(*rgb)
                pdf.set_font("Helvetica", "B", 7)
                # Use "-" in PDF for the en-dash character
                display_lbl = "-" if lbl == "\u2013" else lbl
                pdf.cell(day_col_w, row_h, display_lbl, border=1, fill=True, align="C")

            pdf.ln()

        # Legend
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(100, 116, 139)
        legend_items = [
            ("M - Morning (07-14)", (245, 158, 11)),
            ("E - Evening (14-22)", (139, 92, 246)),
            ("N - Night (22-07)", (14, 165, 233)),
            ("R - Rest", (100, 116, 139)),
            ("RT - Retraining", (16, 185, 129)),
            ("G - General (08-16)", (249, 115, 22)),
            ("- - Super Week", (71, 85, 105)),
        ]
        x_start = pdf.l_margin
        for text, color in legend_items:
            pdf.set_fill_color(*color)
            pdf.set_xy(x_start, pdf.get_y())
            pdf.cell(3, 3, "", fill=True)
            pdf.set_text_color(*color)
            pdf.cell(40, 4, f"  {text}")
            x_start += 40
            if x_start > pdf.w - 50:
                x_start = pdf.l_margin
                pdf.ln(5)

        # Next month
        m_cur += 1
        if m_cur > 12:
            m_cur = 1
            y_cur += 1

    # Footer on last page
    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 6, "Shift Roster App  |  Created by Mr. M  |  Data from 2015-2030", align="C")

    return bytes(pdf.output())


st.markdown("<div style='text-align:center;'>", unsafe_allow_html=True)
pdf_bytes = generate_roster_pdf(roster, crew_id, st.session_state.view_year, st.session_state.view_month, num_months=3)
month_label = f"{calendar.month_name[st.session_state.view_month]}_{st.session_state.view_year}"
pdf_filename = f"Shift_Roster_{month_label}_3months.pdf"

st.download_button(
    label="📥  Download Roster PDF (3 Months)",
    data=pdf_bytes,
    file_name=pdf_filename,
    mime="application/pdf",
    use_container_width=True,
)
st.markdown("</div>", unsafe_allow_html=True)

# Footer
st.markdown("""
<div style='text-align:center;color:#334155;font-size:0.75rem;margin-top:32px;padding-top:16px;border-top:1px solid #1e293b;'>
  Shift Roster App &nbsp;·&nbsp; Created by Mr. M &nbsp;·&nbsp; Data from 2026–2030
</div>
""", unsafe_allow_html=True)
