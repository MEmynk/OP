"""
Order Priority System - Core Logic
-----------------------------------
Google Sheet se order data leta hai, delivery date + kaam ke size ke hisaab se
priority nikalta hai. Yahan sirf logic hai, UI app.py me hai.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd

# --------------------------------------------------------------------------
# Column names (sheet ke headers). Agar sheet me naam badal jaaye to yahan badlo.
# --------------------------------------------------------------------------
COL_SNO = "S.n"
COL_ORDER_NO = "ORDER NO."
COL_ORDER_DATE = "ORDER DATE"
COL_DEL_DATE = "DEL. DATE"
COL_PARTY = "PARTY NAME"
COL_DESC = "DESCRIPTION"
COL_REMARK = "REMARK/DRLIVERRD"

# Sheet me header ka spelling thoda alag ho sakta hai - ye aliases try honge
COLUMN_ALIASES = {
    COL_SNO: ["s.n", "sn", "s no", "s.no", "sr", "sr.no", "serial"],
    COL_ORDER_NO: ["order no.", "order no", "orderno", "order number", "od no"],
    COL_ORDER_DATE: ["order date", "orderdate", "date"],
    COL_DEL_DATE: ["del. date", "del date", "delivery date", "deldate", "dl date"],
    COL_PARTY: ["party name", "party", "partyname", "customer", "client"],
    COL_DESC: ["description", "desc", "item", "items", "work", "details"],
    COL_REMARK: [
        "remark/drliverrd",
        "remark/delivered",
        "remark",
        "remarks",
        "status",
        "remark/status",
    ],
}

# --------------------------------------------------------------------------
# Status detection - REMARK column me status aur note dono mile hue hain,
# isliye keyword se khud detect karte hain.
# --------------------------------------------------------------------------
STATUS_DELIVERED = "Delivered"
STATUS_READY = "Ready"
STATUS_IN_PROCESS = "In Process"
STATUS_PENDING = "Pending"

STATUS_ORDER = [STATUS_PENDING, STATUS_IN_PROCESS, STATUS_READY, STATUS_DELIVERED]

# Order matters: pehle delivered check hoga, phir ready, phir in-process
_DELIVERED_WORDS = [
    "deliver", "delivered", "dilivered", "dlivered", "drliverrd", "despatch",
    "dispatch", "dispatched", "sent", "bhej diya", "bheja", "done", "complete",
    "completed", "gaya", "ho gaya",
]
_READY_WORDS = [
    "ready", "redy", "raedy", "tayyar", "taiyar", "packed", "pack", "ok",
    "finish", "finished", "bn gaya", "ban gaya",
]
_IN_PROCESS_WORDS = [
    "process", "running", "chal", "chalu", "wip", "polish", "welding", "paint",
    "painting", "cutting", "fitting", "repair", "repairing", "reparing",
    "pending work", "started", "start", "shuru", "banna", "bana rahe",
]


def _norm(text) -> str:
    """Text ko lowercase + extra spaces hata kar normalize karta hai."""
    if text is None:
        return ""
    if isinstance(text, float) and math.isnan(text):
        return ""
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def detect_status(remark) -> str:
    """
    REMARK cell padh kar status nikalta hai.
    Ek hi cell me status + note dono ho sakte hain, jaise:
      'Set no.4 Reggin DELIVERED'  -> Delivered
      'S.K LOGO/ READY'            -> Ready
      'GOLDAN POLISH + WELDING'    -> In Process
      '' (khali)                   -> Pending
    """
    t = _norm(remark)
    if not t:
        return STATUS_PENDING

    # "not delivered" / "nahi bheja" jaise negative case ko delivered mat samjho
    negated = bool(re.search(
        r"\b(not|nahi|nhi|no)\s+\w*\s*"
        r"(deliver\w*|ready|done|bhej\w*|bheja|gaya|complete\w*)", t))

    if not negated and any(w in t for w in _DELIVERED_WORDS):
        return STATUS_DELIVERED
    if any(w in t for w in _READY_WORDS):
        return STATUS_READY
    if any(w in t for w in _IN_PROCESS_WORDS):
        return STATUS_IN_PROCESS
    # Kuch likha hai par pehchana nahi gaya -> matlab kaam par kuch note hai
    return STATUS_IN_PROCESS


def is_open(status: str) -> bool:
    """Delivered ke alawa sab kaam abhi baaki hai."""
    return status != STATUS_DELIVERED


# --------------------------------------------------------------------------
# Date parsing - sheet me d/m/yyyy format hai (1/6/2026 = 1 June 2026)
# --------------------------------------------------------------------------
def parse_date(value):
    """Sheet ki date ko python date me badalta hai. Na parse ho to None."""
    if value is None:
        return None
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, float) and math.isnan(value):
        return None

    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none", "-", "--"}:
        return None

    # Google Sheet ka serial number (kabhi kabhi aata hai)
    if re.fullmatch(r"\d{5}", text):
        try:
            return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(text))).date()
        except Exception:
            pass

    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%d/%m/%y", "%d-%m-%y",
        "%Y-%m-%d", "%Y/%m/%d",
        "%d %b %Y", "%d %B %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------
# Kaam ka size - DESCRIPTION me se quantity nikalna
# --------------------------------------------------------------------------
_QTY_PATTERN = re.compile(
    r"(\d{1,5})\s*[-–—]?\s*(?:pcs?|pieces?|set|sets|nos?|no\.)\b", re.IGNORECASE
)
_LEADING_NUM = re.compile(r"^\s*(\d{1,5})\s*[-–—]")


def extract_quantity(description) -> int:
    """
    DESCRIPTION me se total pieces ka anuman lagata hai.
    Har line alag item hoti hai, jaise:
      '20 PCS- TITALI COUNTER'  -> 20
      '8 PCS- RISER (SS)'       -> 8
      '5-Riser Top Repairig'    -> 5
    Total = sabka jod.
    """
    text = str(description or "")
    if not text.strip():
        return 0

    total = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        matches = _QTY_PATTERN.findall(line)
        if matches:
            # Ek line me kai number ho sakte hain (jaise '18 X 36' size) -
            # sirf pehla wala quantity maante hain
            total += int(matches[0])
            continue
        lead = _LEADING_NUM.match(line)
        if lead:
            total += int(lead.group(1))
            continue
        # Koi number nahi mila par line hai -> kam se kam 1 item
        total += 1
    return total


def estimate_work_days(quantity: int, pieces_per_day: int, min_days: int = 1,
                       max_days: int = 30) -> int:
    """
    Quantity se anuman lagata hai ki kitne din ka kaam hai.
    pieces_per_day = ek din me factory kitne piece nipta leti hai (sidebar se set hota hai).
    """
    if pieces_per_day <= 0:
        pieces_per_day = 1
    days = math.ceil(max(quantity, 1) / pieces_per_day)
    return max(min_days, min(days, max_days))


# --------------------------------------------------------------------------
# Priority bands
# --------------------------------------------------------------------------
BAND_OVERDUE = "Overdue"
BAND_CRITICAL = "Critical"
BAND_SOON = "Soon"
BAND_PLANNED = "Planned"
BAND_NO_DATE = "Date Missing"

BAND_META = {
    BAND_OVERDUE:  {"label": "Overdue",      "hindi": "डेट निकल गई",   "color": "#b3261e", "emoji": "🔴"},
    BAND_CRITICAL: {"label": "Critical",     "hindi": "सबसे पहले",      "color": "#e8590c", "emoji": "🟠"},
    BAND_SOON:     {"label": "Soon",         "hindi": "जल्दी शुरू करो", "color": "#c9a227", "emoji": "🟡"},
    BAND_PLANNED:  {"label": "Planned",      "hindi": "समय है",         "color": "#2f7d32", "emoji": "🟢"},
    BAND_NO_DATE:  {"label": "Date Missing", "hindi": "डेट भरनी है",    "color": "#6b46c1", "emoji": "🟣"},
}

BAND_ORDER = [BAND_OVERDUE, BAND_CRITICAL, BAND_SOON, BAND_PLANNED, BAND_NO_DATE]


def _is_missing(v) -> bool:
    """None ya NaN dono ko missing maano (pandas NaN de deta hai)."""
    if v is None:
        return True
    try:
        return bool(pd.isna(v))
    except Exception:
        return False


def band_for(days_left, slack) -> str:
    """
    days_left = delivery date me kitne din bache
    slack     = kitne din aur ruk sakte hain shuru karne ke liye
                (days_left - kaam ke din). Negative = abhi shuru karo.
    """
    if _is_missing(days_left):
        return BAND_NO_DATE
    if days_left < 0:
        return BAND_OVERDUE
    if not _is_missing(slack) and slack <= 0:
        return BAND_CRITICAL
    if days_left <= 2:
        return BAND_CRITICAL
    if not _is_missing(slack) and slack <= 3:
        return BAND_SOON
    if days_left <= 5:
        return BAND_SOON
    return BAND_PLANNED


# --------------------------------------------------------------------------
# Column mapping
# --------------------------------------------------------------------------
def map_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Sheet ke headers ko standard naam par le aata hai."""
    rename = {}
    used = set()
    lower_cols = {c: _norm(c) for c in df.columns}

    for target, aliases in COLUMN_ALIASES.items():
        for col, low in lower_cols.items():
            if col in used:
                continue
            if low == _norm(target) or low in aliases:
                rename[col] = target
                used.add(col)
                break
        else:
            # exact match nahi mila -> partial match try karo
            for col, low in lower_cols.items():
                if col in used or not low:
                    continue
                if any(a in low or low in a for a in aliases):
                    rename[col] = target
                    used.add(col)
                    break

    out = df.rename(columns=rename)
    for target in COLUMN_ALIASES:
        if target not in out.columns:
            out[target] = ""
    return out


def clean_raw_frame(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sheet me upar title row ('ORDER SHEET') aur khali rows hoti hain.
    Asli header row dhoond kar wahan se data lete hain.
    """
    df = df.copy()
    df.columns = [str(c) for c in df.columns]

    # Agar headers 'Unnamed: 0' type hain to asli header row dhoondo
    header_like = sum(
        1 for c in df.columns if _norm(c) in {a for al in COLUMN_ALIASES.values() for a in al}
    )
    if header_like < 3:
        for i in range(min(len(df), 12)):
            row_vals = [_norm(v) for v in df.iloc[i].tolist()]
            hits = sum(
                1 for v in row_vals
                if v in {a for al in COLUMN_ALIASES.values() for a in al}
            )
            if hits >= 3:
                new_cols = [str(v) if str(v).strip() else f"col{j}"
                            for j, v in enumerate(df.iloc[i].tolist())]
                df = df.iloc[i + 1:].copy()
                df.columns = new_cols
                break

    df = map_columns(df)
    # Puri tarah khali rows hatao
    df = df[~(df[COL_ORDER_NO].astype(str).str.strip().isin(["", "nan", "None"])
              & df[COL_PARTY].astype(str).str.strip().isin(["", "nan", "None"]))]
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------
# Main transform
# --------------------------------------------------------------------------
@dataclass
class Settings:
    pieces_per_day: int = 60      # ek din me kitne piece ka kaam nipat jata hai
    today: date | None = None     # testing ke liye override kar sakte hain


def build_priority_table(raw: pd.DataFrame, settings: Settings | None = None) -> pd.DataFrame:
    """Raw sheet data -> priority ke saath ready table."""
    settings = settings or Settings()
    today = settings.today or date.today()

    df = clean_raw_frame(raw)
    if df.empty:
        return pd.DataFrame(columns=[
            COL_ORDER_NO, COL_PARTY, COL_DESC, COL_REMARK, "order_date",
            "del_date", "status", "quantity", "work_days", "start_by",
            "days_left", "slack", "band", "priority_rank",
        ])

    df["order_date"] = df[COL_ORDER_DATE].map(parse_date)
    df["del_date"] = df[COL_DEL_DATE].map(parse_date)
    df["status"] = df[COL_REMARK].map(detect_status)
    df["quantity"] = df[COL_DESC].map(extract_quantity)
    df["work_days"] = df["quantity"].map(
        lambda q: estimate_work_days(int(q), settings.pieces_per_day)
    )

    df["days_left"] = df["del_date"].map(
        lambda d: (d - today).days if d is not None else None
    )
    df["start_by"] = df.apply(
        lambda r: (r["del_date"] - timedelta(days=int(r["work_days"])))
        if r["del_date"] is not None else None,
        axis=1,
    )
    df["slack"] = df.apply(
        lambda r: (r["days_left"] - int(r["work_days"]))
        if r["days_left"] is not None else None,
        axis=1,
    )
    df["band"] = df.apply(lambda r: band_for(r["days_left"], r["slack"]), axis=1)

    # Sorting: pehle band ke hisaab se, phir slack, phir delivery date
    band_rank = {b: i for i, b in enumerate(BAND_ORDER)}
    df["_band_rank"] = df["band"].map(band_rank).fillna(99)
    df["_slack_sort"] = df["slack"].map(lambda s: 9999 if _is_missing(s) else s)
    df["_date_sort"] = df["del_date"].map(
        lambda d: date(2099, 1, 1) if _is_missing(d) else d
    )
    # Ready ka kaam ho chuka hai (sirf bhejna baaki), Delivered khatam -
    # dono neeche jaayenge, upar wahi jispar abhi mehnat lagni hai
    df["_stage_sort"] = df["status"].map(
        {STATUS_PENDING: 0, STATUS_IN_PROCESS: 0, STATUS_READY: 1, STATUS_DELIVERED: 2}
    ).fillna(0)

    df = df.sort_values(
        by=["_stage_sort", "_band_rank", "_slack_sort", "_date_sort"],
        kind="stable",
    ).reset_index(drop=True)

    # Rank sirf pending kaam par (delivered ko rank ki zaroorat nahi)
    open_mask = df["status"] != STATUS_DELIVERED
    df["priority_rank"] = None
    df.loc[open_mask, "priority_rank"] = range(1, int(open_mask.sum()) + 1)

    return df.drop(columns=["_band_rank", "_slack_sort", "_date_sort", "_stage_sort"])


def summary_stats(df: pd.DataFrame, today: date | None = None) -> dict:
    """Dashboard ke upar wale cards ke numbers."""
    today = today or date.today()
    open_df = df[df["status"] != STATUS_DELIVERED]

    def _count(mask) -> int:
        return int(mask.sum()) if len(open_df) else 0

    if open_df.empty:
        return {"total_open": 0, "overdue": 0, "today": 0, "this_week": 0,
                "start_now": 0, "no_date": 0,
                "delivered": int((df["status"] == STATUS_DELIVERED).sum())}

    days = open_df["days_left"]
    return {
        "total_open": len(open_df),
        "overdue": _count(days.map(lambda d: not _is_missing(d) and d < 0)),
        "today": _count(days.map(lambda d: not _is_missing(d) and d == 0)),
        "this_week": _count(days.map(lambda d: not _is_missing(d) and 0 <= d <= 7)),
        "start_now": _count(
            open_df["slack"].map(lambda s: not _is_missing(s) and s <= 0)
        ),
        "no_date": _count(open_df["del_date"].map(_is_missing)),
        "delivered": int((df["status"] == STATUS_DELIVERED).sum()),
    }
