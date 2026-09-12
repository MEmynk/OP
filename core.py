"""
Order Priority System - Core Logic
-----------------------------------
Google Sheet se order data leta hai aur delivery date ke hisaab se priority
nikalta hai. Yahan sirf logic hai, UI app.py me hai.

Priority ka rule (v3 - simple):
  1. Jiski delivery date pehle hai, uska kaam pehle
  2. Ek hi date par do order? Jisme maal (quantity) zyada hai wo pehle
  3. Ready / Party Side Delayed / Delivered - ye priority list me aate hi nahi
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime

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
COL_REMARK = "REMARK"
COL_STATUS = "STATUS"

# Sheet me header ka spelling thoda alag ho sakta hai - ye aliases try honge
COLUMN_ALIASES = {
    COL_SNO: ["s.n", "sn", "s no", "s.no", "sr", "sr.no", "serial"],
    COL_ORDER_NO: ["order no.", "order no", "orderno", "order number", "od no"],
    COL_ORDER_DATE: ["order date", "orderdate", "date"],
    COL_DEL_DATE: ["del. date", "del date", "delivery date", "deldate", "dl date"],
    COL_PARTY: ["party name", "party", "partyname", "customer", "client"],
    COL_DESC: ["description", "desc", "item", "items", "work", "details"],
    COL_REMARK: [
        "remark", "remarks", "remark/drliverrd", "remark/delivered", "note", "notes",
    ],
    COL_STATUS: ["status", "stats", "order status", "current status", "sthiti"],
}

# --------------------------------------------------------------------------
# Status - REMARK column me status aur note dono ek saath likhe hote hain,
# isliye keyword se khud pehchante hain.
# --------------------------------------------------------------------------
STATUS_DELIVERED = "Delivered"
STATUS_PARTY_DELAYED = "Party Side Delayed"
STATUS_READY = "Ready"
STATUS_IN_PROCESS = "In Process"
STATUS_PENDING = "Pending"

STATUS_ORDER = [
    STATUS_PENDING, STATUS_IN_PROCESS, STATUS_READY,
    STATUS_PARTY_DELAYED, STATUS_DELIVERED,
]

# Party ki taraf se ruka hua - sabse pehle ye check hota hai
_PARTY_DELAY_WORDS = [
    "party side delayed", "party side delay", "party side", "party delayed",
    "party delay", "party ki taraf", "party ne mana", "party nahi aayi",
    "party nahi aaya", "party ne roka", "customer delay", "customer side",
    "psd", "hold by party", "party hold",
]
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


def _is_missing(v) -> bool:
    """None ya NaN dono ko missing maano (pandas NaN de deta hai)."""
    if v is None:
        return True
    try:
        return bool(pd.isna(v))
    except Exception:
        return False


# STATUS column me jo likha ho uske liye seedha mapping.
# Chhoti-moti spelling galti bhi chal jaayegi.
_STATUS_COLUMN_MAP = [
    (STATUS_PARTY_DELAYED, ["party delay", "party side delay", "party side delayed",
                            "party delayed", "party hold", "psd", "customer delay"]),
    (STATUS_DELIVERED,     ["delivered", "deliverd", "dilivered", "delivery done",
                            "dispatched", "despatched", "done"]),
    (STATUS_READY,         ["ready", "redy", "reddy", "raedy", "tayyar", "taiyar"]),
    (STATUS_IN_PROCESS,    ["in process", "inprocess", "in-process", "process",
                            "processing", "running", "wip", "chalu"]),
    (STATUS_PENDING,       ["pending", "panding", "baaki", "not started"]),
]


def status_from_column(value) -> str | None:
    """
    STATUS column ki value ko standard status me badalta hai.
    Khali ho ya samajh na aaye to None - phir REMARK se guess karenge.
    """
    t = _norm(value)
    if not t:
        return None
    # Beech me space/typo ho to bhi pakde: "DELI VERED" -> "delivered"
    tight = re.sub(r"[^a-z0-9]", "", t)
    for status, words in _STATUS_COLUMN_MAP:
        for w in words:
            if w in t or re.sub(r"[^a-z0-9]", "", w) in tight:
                return status
    return None


def detect_status(remark) -> str:
    """
    REMARK cell padh kar status nikalta hai. Misaal:
      'PARTY SIDE DELAYED'         -> Party Side Delayed
      'Set no.4 Reggin DELIVERED'  -> Delivered
      'S.K LOGO/ READY'            -> Ready
      'GOLDAN POLISH + WELDING'    -> In Process
      '' (khali)                   -> Pending
    """
    t = _norm(remark)
    if not t:
        return STATUS_PENDING

    # Party ki taraf se ruka hai - ye sabse pehle, kyunki aksar
    # "READY BUT PARTY SIDE DELAYED" jaisa likha hota hai
    if any(w in t for w in _PARTY_DELAY_WORDS):
        return STATUS_PARTY_DELAYED

    # "not delivered" / "nahi bheja" ko delivered mat samjho
    negated = bool(re.search(
        r"\b(not|nahi|nhi|no)\s+\w*\s*"
        r"(deliver\w*|ready|done|bhej\w*|bheja|gaya|complete\w*)", t))

    if not negated and any(w in t for w in _DELIVERED_WORDS):
        return STATUS_DELIVERED
    if any(w in t for w in _READY_WORDS):
        return STATUS_READY
    if any(w in t for w in _IN_PROCESS_WORDS):
        return STATUS_IN_PROCESS
    # Kuch likha hai par pehchana nahi gaya -> kaam par koi note hai
    return STATUS_IN_PROCESS


def is_open(status: str) -> bool:
    """Delivered ke alawa sab abhi khatam nahi hue."""
    return status != STATUS_DELIVERED


def is_work_pending(status: str) -> bool:
    """
    Factory me abhi mehnat lagni baaki hai?

    Sirf Pending aur In Process. Ready ka maal ban chuka hai aur showroom me
    rakha hai; Party Side Delayed party ki taraf se ruka hai. In dono ka delay
    hamara nahi, isliye ye priority list me nahi aate.
    """
    return status in (STATUS_PENDING, STATUS_IN_PROCESS)


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
# Quantity - DESCRIPTION me se maal ki ginti
# (sirf same-date wale orders ko aapas me compare karne ke liye)
# --------------------------------------------------------------------------
_QTY_PATTERN = re.compile(
    r"(\d{1,5})\s*[-–—]?\s*(?:pcs?|pieces?|set|sets|nos?|no\.)\b", re.IGNORECASE
)
_LEADING_NUM = re.compile(r"^\s*(\d{1,5})\s*[-–—]")


def extract_quantity(description) -> int:
    """
    DESCRIPTION ki har line se pehla number jodta hai:
      '20 PCS- TITALI COUNTER'  -> 20
      '8 PCS- RISER (SS)'       -> 8
      '5-Riser Top Repairig'    -> 5
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
        total += 1  # number nahi mila par line hai -> kam se kam 1 item
    return total


# --------------------------------------------------------------------------
# Priority bands - sirf delivery date par
# --------------------------------------------------------------------------
BAND_OVERDUE = "Overdue"
BAND_CRITICAL = "Critical"
BAND_SOON = "Soon"
BAND_PLANNED = "Planned"
BAND_NO_DATE = "Date Missing"

BAND_META = {
    BAND_OVERDUE:  {"label": "Overdue",      "hindi": "डेट निकल गई",  "color": "#b3261e", "emoji": "🔴"},
    BAND_CRITICAL: {"label": "Critical",     "hindi": "सबसे पहले",     "color": "#e8590c", "emoji": "🟠"},
    BAND_SOON:     {"label": "Soon",         "hindi": "जल्दी करो",     "color": "#c9a227", "emoji": "🟡"},
    BAND_PLANNED:  {"label": "Planned",      "hindi": "समय है",        "color": "#2f7d32", "emoji": "🟢"},
    BAND_NO_DATE:  {"label": "Date Missing", "hindi": "डेट भरनी है",   "color": "#6b46c1", "emoji": "🟣"},
}

BAND_ORDER = [BAND_OVERDUE, BAND_CRITICAL, BAND_SOON, BAND_PLANNED, BAND_NO_DATE]


def band_for(days_left) -> str:
    """days_left = delivery date me kitne din bache."""
    if _is_missing(days_left):
        return BAND_NO_DATE
    if days_left < 0:
        return BAND_OVERDUE
    if days_left <= 2:
        return BAND_CRITICAL
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
    all_aliases = {a for al in COLUMN_ALIASES.values() for a in al}

    header_like = sum(1 for c in df.columns if _norm(c) in all_aliases)
    if header_like < 3:
        for i in range(min(len(df), 12)):
            row_vals = [_norm(v) for v in df.iloc[i].tolist()]
            if sum(1 for v in row_vals if v in all_aliases) >= 3:
                new_cols = [str(v) if str(v).strip() else f"col{j}"
                            for j, v in enumerate(df.iloc[i].tolist())]
                df = df.iloc[i + 1:].copy()
                df.columns = new_cols
                break

    df = map_columns(df)
    df = df[~(df[COL_ORDER_NO].astype(str).str.strip().isin(["", "nan", "None"])
              & df[COL_PARTY].astype(str).str.strip().isin(["", "nan", "None"]))]
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------
# Main transform
# --------------------------------------------------------------------------
@dataclass
class Settings:
    today: date | None = None     # testing ke liye override kar sakte hain


def build_priority_table(raw: pd.DataFrame, settings: Settings | None = None) -> pd.DataFrame:
    """Raw sheet data -> priority ke saath ready table."""
    settings = settings or Settings()
    today = settings.today or date.today()

    df = clean_raw_frame(raw)
    if df.empty:
        return pd.DataFrame(columns=[
            COL_ORDER_NO, COL_PARTY, COL_DESC, COL_REMARK, COL_STATUS, "order_date",
            "del_date", "status", "quantity", "days_left", "band", "priority_rank",
        ])

    df["order_date"] = df[COL_ORDER_DATE].map(parse_date)
    df["del_date"] = df[COL_DEL_DATE].map(parse_date)
    # Sheet me alag STATUS column hai (kahin bhi kuch bhara hai) to wahi sach hai.
    # Us haalat me khali STATUS ka matlab Pending - REMARK ke text se guess
    # nahi karenge, warna "43X24.4" jaisa note galat status bana deta hai.
    has_status_col = df[COL_STATUS].map(lambda v: bool(_norm(v))).any()
    if has_status_col:
        df["status"] = [
            status_from_column(v) or STATUS_PENDING for v in df[COL_STATUS]
        ]
    else:
        # Purani sheet (sirf REMARK column) - keyword se andaza
        df["status"] = df[COL_REMARK].map(detect_status)
    df["quantity"] = df[COL_DESC].map(extract_quantity)
    df["days_left"] = df["del_date"].map(
        lambda d: (d - today).days if d is not None else None
    )
    df["band"] = df["days_left"].map(band_for)

    # ---- Sorting ----
    # 1. jinpar kaam baaki hai wo upar, phir Ready/Party-delayed, aakhir me Delivered
    df["_stage_sort"] = df["status"].map({
        STATUS_PENDING: 0, STATUS_IN_PROCESS: 0,
        STATUS_READY: 1, STATUS_PARTY_DELAYED: 1,
        STATUS_DELIVERED: 2,
    }).fillna(0)
    # 2. band (overdue sabse upar)
    band_rank = {b: i for i, b in enumerate(BAND_ORDER)}
    df["_band_rank"] = df["band"].map(band_rank).fillna(99)
    # 3. delivery date - jo pehle hai wo upar
    df["_date_sort"] = df["del_date"].map(
        lambda d: date(2099, 1, 1) if _is_missing(d) else d
    )
    # 4. ek hi date par? jisme maal zyada hai wo pehle
    df["_qty_sort"] = -df["quantity"].astype(int)

    df = df.sort_values(
        by=["_stage_sort", "_band_rank", "_date_sort", "_qty_sort"],
        kind="stable",
    ).reset_index(drop=True)

    # Rank sirf us kaam par jo abhi factory me baaki hai
    work_mask = df["status"].map(is_work_pending)
    df["priority_rank"] = None
    df.loc[work_mask, "priority_rank"] = range(1, int(work_mask.sum()) + 1)

    return df.drop(columns=["_stage_sort", "_band_rank", "_date_sort", "_qty_sort"])


def summary_stats(df: pd.DataFrame, today: date | None = None) -> dict:
    """Dashboard ke upar wale cards ke numbers."""
    today = today or date.today()
    work_df = df[df["status"].map(is_work_pending)]
    ready_n = int((df["status"] == STATUS_READY).sum())
    party_n = int((df["status"] == STATUS_PARTY_DELAYED).sum())
    done_n = int((df["status"] == STATUS_DELIVERED).sum())

    base = {
        "total_open": len(work_df), "overdue": 0, "today": 0, "this_week": 0,
        "no_date": 0, "ready_waiting": ready_n, "party_delayed": party_n,
        "delivered": done_n,
    }
    if work_df.empty:
        return base

    days = work_df["days_left"]
    base.update({
        "overdue": int(days.map(lambda d: not _is_missing(d) and d < 0).sum()),
        "today": int(days.map(lambda d: not _is_missing(d) and d == 0).sum()),
        "this_week": int(days.map(lambda d: not _is_missing(d) and 0 <= d <= 7).sum()),
        "no_date": int(work_df["del_date"].map(_is_missing).sum()),
    })
    return base
