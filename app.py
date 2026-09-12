"""
Order Priority System - Streamlit Dashboard
--------------------------------------------
Chalane ke liye:   streamlit run app.py
"""

from __future__ import annotations

import html as _html
import io
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import core
from core import (
    BAND_META, BAND_ORDER, COL_DESC, COL_ORDER_NO, COL_PARTY, COL_REMARK,
    STATUS_DELIVERED, STATUS_IN_PROCESS, STATUS_PENDING, STATUS_READY,
    Settings, build_priority_table, summary_stats,
)

st.set_page_config(
    page_title="Order Priority - Pathan Steel",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
st.markdown("""
<style>
  .block-container {padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1400px;}
  #MainMenu, footer {visibility: hidden;}

  .hero {
    background: linear-gradient(135deg, #1f2937 0%, #374151 100%);
    color: #fff; border-radius: 14px; padding: 18px 22px; margin-bottom: 18px;
  }
  .hero h1 {margin: 0; font-size: 1.45rem; font-weight: 700; letter-spacing: .2px;}
  .hero p {margin: 4px 0 0; opacity: .78; font-size: .86rem;}

  .stat-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px; margin-bottom: 20px;
  }
  .stat {
    background: #ffffff; color: #0f172a;
    border: 1px solid rgba(0,0,0,.08);
    border-left: 6px solid #94a3b8; border-radius: 12px; padding: 12px 15px;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
  }
  .stat .top {display: flex; align-items: baseline; gap: 8px;}
  .stat .n {font-size: 2rem; font-weight: 800; line-height: 1;}
  .stat .icon {font-size: 1rem;}
  /* label har theme me dikhe - isliye rang khud tay kiya hai, inherit nahi */
  .stat .l {font-size: .88rem; font-weight: 700; color: #0f172a; margin-top: 6px;}
  .stat .s {font-size: .76rem; color: #475569; margin-top: 2px; line-height: 1.35;}

  .card {
    border: 1px solid rgba(0,0,0,.09); border-left: 6px solid #94a3b8;
    border-radius: 12px; padding: 13px 16px; margin-bottom: 11px;
    background: rgba(255,255,255,.55);
  }
  .card-head {display: flex; flex-wrap: wrap; align-items: center; gap: 9px;}
  .rank {
    background: #1f2937; color: #fff; border-radius: 8px; min-width: 30px;
    height: 26px; display: inline-flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: .82rem; padding: 0 7px;
  }
  .party {font-weight: 700; font-size: 1.02rem;}
  .ordno {font-size: .78rem; opacity: .6; font-family: ui-monospace, monospace;}
  .pill {
    font-size: .7rem; font-weight: 700; padding: 3px 9px; border-radius: 20px;
    color: #fff; text-transform: uppercase; letter-spacing: .4px;
  }
  .pill-soft {
    font-size: .7rem; font-weight: 600; padding: 3px 9px; border-radius: 20px;
    background: rgba(0,0,0,.07); letter-spacing: .3px;
  }
  .desc {
    font-size: .84rem; opacity: .85; margin-top: 8px; white-space: pre-line;
    line-height: 1.45;
  }
  .meta {font-size: .78rem; opacity: .72; margin-top: 8px;}
  .meta b {opacity: .95;}
  .remark {font-size: .78rem; opacity: .7; margin-top: 5px; font-style: italic;}

  @media print {
    .stApp header, .stSidebar, .stTabs [role="tablist"], .no-print {display: none !important;}
    .card {break-inside: avoid;}
  }
  @media (max-width: 640px) {
    .stat .n {font-size: 1.4rem;}
    .hero h1 {font-size: 1.15rem;}
  }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def safe_secret(key: str, default=None):
    """secrets.toml na ho to bhi app crash na ho."""
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def csv_export_url(sheet_url: str, gid: str = "0") -> str:
    """Normal Google Sheet link ko CSV download link me badalta hai."""
    sheet_url = sheet_url.strip()
    if "/d/" not in sheet_url:
        return sheet_url
    sheet_id = sheet_url.split("/d/")[1].split("/")[0]
    if "gid=" in sheet_url:
        gid = sheet_url.split("gid=")[1].split("&")[0].split("#")[0]
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


@st.cache_data(ttl=120, show_spinner="Google Sheet se data aa raha hai...")
def load_public_sheet(sheet_url: str) -> pd.DataFrame:
    return pd.read_csv(csv_export_url(sheet_url), dtype=str, header=None).fillna("")


@st.cache_data(ttl=120, show_spinner="Google Sheet se data aa raha hai...")
def load_private_sheet(sheet_url: str, worksheet: str, creds_dict: dict) -> pd.DataFrame:
    import gspread  # sirf zaroorat padne par import

    gc = gspread.service_account_from_dict(creds_dict)
    sh = gc.open_by_url(sheet_url)
    ws = sh.worksheet(worksheet) if worksheet else sh.sheet1
    return pd.DataFrame(ws.get_all_values()).fillna("")


def load_data(source: str, sheet_url: str, worksheet: str, upload) -> pd.DataFrame | None:
    if source == "Google Sheet (public link)":
        if not sheet_url:
            return None
        return load_public_sheet(sheet_url)

    if source == "Google Sheet (private / service account)":
        if not sheet_url:
            return None
        creds = safe_secret("gcp_service_account")
        if not creds:
            st.error("secrets.toml me [gcp_service_account] nahi mila. README dekho.")
            return None
        return load_private_sheet(sheet_url, worksheet, dict(creds))

    if source == "File upload (CSV / Excel)":
        if upload is None:
            return None
        if upload.name.lower().endswith((".xlsx", ".xls")):
            return pd.read_excel(upload, dtype=str, header=None).fillna("")
        return pd.read_csv(io.BytesIO(upload.getvalue()), dtype=str, header=None).fillna("")

    # Demo
    return pd.read_csv("sample_orders.csv", dtype=str).fillna("")


# ---------------------------------------------------------------------------
# Sidebar - settings
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Settings")

    source = st.radio(
        "Data kahan se lena hai",
        [
            "Google Sheet (public link)",
            "Google Sheet (private / service account)",
            "File upload (CSV / Excel)",
            "Demo data",
        ],
        index=3,
    )

    sheet_url, worksheet, upload = "", "", None
    if source.startswith("Google Sheet"):
        sheet_url = st.text_input(
            "Sheet ka link",
            value=safe_secret("sheet_url", "") or "",
            placeholder="https://docs.google.com/spreadsheets/d/.../edit",
        )
        if "private" in source:
            worksheet = st.text_input("Worksheet ka naam", value="Order sheet")
    elif source.startswith("File"):
        upload = st.file_uploader("CSV ya Excel file", type=["csv", "xlsx", "xls"])

    st.divider()
    pieces_per_day = st.number_input(
        "Ek din me kitne piece ka kaam? ",
        min_value=1, max_value=2000, value=60, step=10,
        help="Isi se anuman lagta hai ki order kitne din lega aur kab shuru karna hai.",
    )
    horizon = st.slider("Aaj ki list me kitne din aage tak dekhein", 1, 15, 7)
    show_delivered = st.checkbox("Delivered orders bhi dikhao", value=False)

    st.divider()
    if st.button("🔄 Data refresh karo", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption("Data har 2 minute me apne aap refresh hota hai.")


# ---------------------------------------------------------------------------
# Load + build
# ---------------------------------------------------------------------------
raw = None
try:
    raw = load_data(source, sheet_url, worksheet, upload)
except Exception as exc:  # noqa: BLE001
    st.error(f"Data load nahi ho paya: {exc}")
    st.stop()

if raw is None:
    st.info("👈 Bayein taraf se data source chuno (ya sheet ka link daalo).")
    st.stop()

today = date.today()
df = build_priority_table(raw, Settings(pieces_per_day=int(pieces_per_day), today=today))

if df.empty:
    st.warning("Sheet me koi order nahi mila. Column ke naam check karo.")
    st.stop()

stats = summary_stats(df, today)


# ---------------------------------------------------------------------------
# Header + stats
# ---------------------------------------------------------------------------
st.markdown(f"""
<div class="hero">
  <h1>🏭 Order Priority Dashboard</h1>
  <p>{today.strftime('%d %B %Y, %A')} &nbsp;·&nbsp; jiski delivery date pehle hai,
     uska kaam pehle &nbsp;·&nbsp; bade order jaldi shuru ho jaate hain</p>
</div>
""", unsafe_allow_html=True)

cards = [
    ("#b3261e", stats["overdue"], "⏱️", "डेट निकल गई",
     "डिलीवरी डेट बीत चुकी, काम अब भी बाकी"),
    ("#e8590c", stats["start_now"], "🔨", "आज शुरू करो",
     "आज हाथ नहीं लगाया तो डेट निकल जाएगी"),
    ("#c9a227", stats["today"], "🚚", "आज डिलीवरी",
     "आज ही पार्टी को देना है"),
    ("#2563eb", stats["this_week"], "📆", "इस हफ़्ते",
     "अगले 7 दिन में डिलीवरी है"),
    ("#6b46c1", stats["no_date"], "📅", "डेट मिसिंग",
     "शीट में DEL. DATE खाली है — भर दो"),
    ("#475569", stats["total_open"], "📋", "कुल पेंडिंग",
     "जितने ऑर्डर का काम अभी बाकी है"),
    ("#2f7d32", stats["delivered"], "✅", "डिलीवर हो चुके",
     "काम खत्म, पार्टी को चले गए"),
]
st.markdown(
    '<div class="stat-grid">'
    + "".join(
        f'<div class="stat" style="border-left-color:{c}">'
        f'<div class="top"><span class="n" style="color:{c}">{n}</span>'
        f'<span class="icon">{icon}</span></div>'
        f'<div class="l">{label}</div>'
        f'<div class="s">{sub}</div></div>'
        for c, n, icon, label, sub in cards
    )
    + "</div>",
    unsafe_allow_html=True,
)

with st.expander("❓ ये नंबर क्या बताते हैं?"):
    st.markdown(
        "- **डेट निकल गई** — डिलीवरी की तारीख बीत चुकी है पर ऑर्डर अब तक डिलीवर नहीं हुआ। "
        "सबसे पहले यही निपटाओ।\n"
        "- **आज शुरू करो** — इतना काम है कि आज शुरू नहीं किया तो डेट पर पूरा नहीं होगा। "
        "(डिलीवरी डेट − काम के दिन = आज या उससे पहले)\n"
        "- **आज डिलीवरी** — आज ही पार्टी को भेजना है।\n"
        "- **इस हफ़्ते** — अगले 7 दिन के अंदर डिलीवरी वाले ऑर्डर।\n"
        "- **डेट मिसिंग** — शीट के DEL. DATE कॉलम में कुछ नहीं लिखा। "
        "इनकी प्रायोरिटी नहीं निकल सकती, इसलिए भरना ज़रूरी है।\n"
        "- **कुल पेंडिंग** — जो डिलीवर नहीं हुए, सब मिलाकर।\n"
        "- **डिलीवर हो चुके** — खत्म हो चुके ऑर्डर, मेन लिस्ट से हटा दिए गए हैं।\n\n"
        "एक ऑर्डर एक से ज़्यादा डिब्बों में गिना जा सकता है — जैसे आज डिलीवरी वाला "
        "ऑर्डर 'इस हफ़्ते' में भी आएगा।"
    )

if stats["overdue"]:
    st.error(f"⚠️ {stats['overdue']} order ki delivery date nikal chuki hai aur "
             f"kaam abhi baaki hai. Sabse upar dekho.")
if stats["no_date"]:
    st.warning(f"📅 {stats['no_date']} order me delivery date khaali hai — "
               f"sheet me bhar do, tabhi priority sahi lagegi.")


# ---------------------------------------------------------------------------
# Card renderer
# ---------------------------------------------------------------------------
STATUS_COLORS = {
    STATUS_PENDING: "#64748b",
    STATUS_IN_PROCESS: "#2563eb",
    STATUS_READY: "#0d9488",
    STATUS_DELIVERED: "#2f7d32",
}


def esc(value) -> str:
    """Sheet ka text HTML me safe kar deta hai (< > & wagairah)."""
    if core._is_missing(value):
        return ""
    return _html.escape(str(value).strip())


def fmt_days(days) -> str:
    if core._is_missing(days):
        return "डेट नहीं है"
    d = int(days)
    if d < 0:
        return f"{abs(d)} दिन लेट"
    if d == 0:
        return "आज डिलीवरी"
    if d == 1:
        return "कल डिलीवरी"
    return f"{d} दिन बचे"


def start_line(row) -> str:
    if core._is_missing(row["start_by"]):
        return "शुरू करने की तारीख — डेट भरने पर पता चलेगी"
    sb = row["start_by"]
    slack = row["slack"]
    if core._is_missing(slack):
        return f"शुरू करो: {sb.strftime('%d %b')}"
    s = int(slack)
    if s < 0:
        return f"⏰ {abs(s)} दिन पहले ही शुरू हो जाना चाहिए था ({sb.strftime('%d %b')})"
    if s == 0:
        return f"⏰ आज ही शुरू करना है ({sb.strftime('%d %b')})"
    return f"शुरू करो {sb.strftime('%d %b')} तक — {s} दिन की ढील है"


def render_card(row, show_rank: bool = True):
    """
    Ek order ka card. HTML ek hi line me banta hai - agar line ke aage
    4 space aa jaayein to Streamlit use code block samajh kar raw HTML
    dikhane lagta hai, isliye yahan koi indentation nahi hai.
    """
    band = BAND_META.get(row["band"], BAND_META[BAND_ORDER[-1]])
    status = row["status"]
    # Delivered order ko "डेट निकल गई" (laal) dikhana galat lagta hai -
    # uska kaam khatam ho chuka, isliye hara band
    if status == STATUS_DELIVERED:
        band = {"color": "#2f7d32", "emoji": "✅", "hindi": "डिलीवर हो गया"}
    rank = row["priority_rank"]
    rank_html = (
        f'<span class="rank">#{int(rank)}</span>'
        if show_rank and not core._is_missing(rank) else ""
    )
    desc = esc(row.get(COL_DESC, "")).replace("\n", "<br>")
    remark = esc(row.get(COL_REMARK, ""))
    party = esc(row.get(COL_PARTY, ""))
    ordno = esc(row.get(COL_ORDER_NO, ""))
    del_txt = (row["del_date"].strftime("%d %b %Y")
               if not core._is_missing(row["del_date"]) else "—")
    status_color = STATUS_COLORS.get(status, "#64748b")

    html = (
        f'<div class="card" style="border-left-color:{band["color"]}">'
        f'<div class="card-head">{rank_html}'
        f'<span class="party">{party}</span>'
        f'<span class="ordno">{ordno}</span>'
        f'<span class="pill" style="background:{band["color"]}">'
        f'{band["emoji"]} {band["hindi"]}</span>'
        f'<span class="pill" style="background:{status_color}">{status}</span>'
        + (f'<span class="pill-soft">{fmt_days(row["days_left"])}</span>'
           if status != STATUS_DELIVERED else "")
        + '</div>'
        f'<div class="desc">{desc}</div>'
        f'<div class="meta">📦 <b>{int(row["quantity"])}</b> pcs &nbsp;·&nbsp; '
        f'🛠️ लगभग <b>{int(row["work_days"])}</b> दिन का काम &nbsp;·&nbsp; '
        f'🚚 डिलीवरी <b>{del_txt}</b><br>{esc(start_line(row))}</div>'
        + (f'<div class="remark">📝 {remark}</div>' if remark else "")
        + '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
open_df = df[df["status"] != STATUS_DELIVERED].copy()
done_df = df[df["status"] == STATUS_DELIVERED].copy()

st.markdown('<div class="no-print"></div>', unsafe_allow_html=True)
fc1, fc2, fc3 = st.columns([2, 2, 2])
with fc1:
    search = st.text_input("🔍 पार्टी / ऑर्डर नंबर / आइटम ढूँढो", "")
with fc2:
    status_pick = st.multiselect(
        "स्टेटस", [STATUS_PENDING, STATUS_IN_PROCESS, STATUS_READY], []
    )
with fc3:
    band_pick = st.multiselect(
        "प्रायोरिटी", [BAND_META[b]["hindi"] for b in BAND_ORDER], []
    )


def apply_filters(d: pd.DataFrame, use_status: bool = True) -> pd.DataFrame:
    """Search + status + priority filter. Delivered tab me status filter
    ka matlab nahi banta, isliye wahan use_status=False."""
    out = d
    if out.empty:
        return out
    if search.strip():
        q = search.strip().lower()
        hay = (out[COL_PARTY].astype(str) + " " + out[COL_ORDER_NO].astype(str)
               + " " + out[COL_DESC].astype(str) + " " + out[COL_REMARK].astype(str))
        out = out[hay.str.lower().str.contains(q, na=False)]
    if use_status and status_pick:
        out = out[out["status"].isin(status_pick)]
    if band_pick:
        wanted = [b for b in BAND_ORDER if BAND_META[b]["hindi"] in band_pick]
        out = out[out["band"].isin(wanted)]
    return out


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_today, tab_all, tab_party, tab_missing, tab_done, tab_table = st.tabs([
    f"🔥 आज का काम",
    f"📋 पूरी प्रायोरिटी लिस्ट ({len(open_df)})",
    "👥 पार्टी के हिसाब से",
    f"📅 डेट मिसिंग ({stats['no_date']})",
    f"✅ डिलीवर हो चुके ({len(done_df)})",
    "📊 टेबल / डाउनलोड",
])

with tab_today:
    today_df = apply_filters(open_df)
    urgent = today_df[
        today_df.apply(
            lambda r: (not core._is_missing(r["slack"]) and r["slack"] <= 0)
            or (not core._is_missing(r["days_left"]) and r["days_left"] <= horizon),
            axis=1,
        )
    ] if not today_df.empty else today_df
    st.caption(f"जिन पर आज मेहनत लगनी है — {len(urgent)} ऑर्डर "
               f"(अगले {horizon} दिन + जो पहले ही शुरू होने चाहिए थे)")
    if urgent.empty:
        st.success("🎉 अगले कुछ दिनों में कोई अर्जेंट डिलीवरी नहीं है। आगे के ऑर्डर पर काम बढ़ाओ।")
    for _, row in urgent.iterrows():
        render_card(row)
    st.caption("💡 इस पेज को Ctrl+P दबाकर प्रिंट कर सकते हो — कारीगरों को देने के लिए।")

with tab_all:
    filtered = apply_filters(open_df)
    st.caption(f"{len(filtered)} ऑर्डर · ऊपर से नीचे यही क्रम है काम का")
    for _, row in filtered.iterrows():
        render_card(row)

with tab_party:
    filtered = apply_filters(open_df)
    for party, grp in filtered.groupby(COL_PARTY, sort=False):
        total_q = int(grp["quantity"].sum())
        st.markdown(f"#### {party} — {len(grp)} ऑर्डर, {total_q} pcs")
        for _, row in grp.iterrows():
            render_card(row)

with tab_missing:
    md = apply_filters(open_df)
    missing = md[md["del_date"].map(core._is_missing)] if not md.empty else md
    if missing.empty:
        st.success("✅ सभी पेंडिंग ऑर्डर में डिलीवरी डेट भरी हुई है।")
    else:
        st.warning("इनकी डिलीवरी डेट शीट में खाली है — भरो तभी सही प्रायोरिटी मिलेगी।")
    for _, row in missing.iterrows():
        render_card(row, show_rank=False)

with tab_done:
    if not show_delivered:
        st.info("साइडबार में 'Delivered orders bhi dikhao' ऑन करो।")
    else:
        dd = apply_filters(done_df, use_status=False)
        st.caption(f"{len(dd)} ऑर्डर")
        for _, row in dd.iterrows():
            render_card(row, show_rank=False)

with tab_table:
    tdf = apply_filters(df) if (search.strip() or status_pick or band_pick) else df
    if len(tdf) != len(df):
        st.caption(f"फ़िल्टर लगा है — {len(tdf)} / {len(df)} ऑर्डर")
    view = tdf[[
        "priority_rank", COL_ORDER_NO, COL_PARTY, "del_date", "days_left",
        "status", "band", "quantity", "work_days", "start_by", COL_DESC, COL_REMARK,
    ]].rename(columns={
        "priority_rank": "Priority", "del_date": "Delivery Date",
        "days_left": "Days Left", "status": "Status", "band": "Band",
        "quantity": "Qty", "work_days": "Work Days", "start_by": "Start By",
    })
    st.dataframe(view, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ CSV डाउनलोड करो",
        view.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"order_priority_{today:%Y%m%d}.csv",
        mime="text/csv",
    )

st.caption("Order Priority System · डेटा सीधे Google Sheet से आता है — शीट बदलो, "
           "यहाँ Refresh दबाओ।")