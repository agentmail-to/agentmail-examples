"""
CSV-backed prospect tracker.

prospects.csv has the following columns (header row required):
  email, name, role, company, hook, status, first_touch_at,
  followup_at, replied_at, classification, thread_id

Drop new prospects in by editing the CSV. The agent picks up rows where
`status` is empty or 'queued' on its next polling cycle.
"""

import csv
from datetime import datetime, timezone
from pathlib import Path

PROSPECTS_FILE = Path("prospects.csv")
LOG_FILE = Path("gtm_log.csv")

COLUMNS = [
    "email", "name", "role", "company", "hook",
    "status", "first_touch_at", "followup_at",
    "replied_at", "classification", "thread_id",
]

LOG_COLUMNS = [
    "timestamp_utc", "action", "prospect_email", "classification",
    "thread_id", "note",
]


# --- prospects --------------------------------------------------------------


def load_all() -> list[dict]:
    if not PROSPECTS_FILE.exists():
        return []
    with PROSPECTS_FILE.open(newline="", encoding="utf-8") as f:
        return [_normalize(r) for r in csv.DictReader(f)]


def _normalize(row: dict) -> dict:
    """Ensure all expected columns exist, defaulting to empty string."""
    return {col: (row.get(col) or "").strip() for col in COLUMNS}


def save_all(rows: list[dict]) -> None:
    with PROSPECTS_FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})


def update_prospect(email: str, **fields) -> dict | None:
    rows = load_all()
    target = None
    for r in rows:
        if r["email"].lower() == email.lower():
            r.update(fields)
            target = r
            break
    if target:
        save_all(rows)
    return target


def find_by_thread(thread_id: str) -> dict | None:
    for r in load_all():
        if r["thread_id"] == thread_id:
            return r
    return None


def queued_prospects() -> list[dict]:
    return [r for r in load_all() if r["status"] in ("", "queued")]


def followups_due(after_hours: int) -> list[dict]:
    """Prospects who got a first touch >N hours ago and haven't been followed up
    or replied. Returns rows where status == 'first_touch_sent'."""
    cutoff = datetime.now(timezone.utc).timestamp() - after_hours * 3600
    out = []
    for r in load_all():
        if r["status"] != "first_touch_sent":
            continue
        if not r["first_touch_at"]:
            continue
        try:
            ts = datetime.fromisoformat(r["first_touch_at"]).timestamp()
        except Exception:
            continue
        if ts <= cutoff:
            out.append(r)
    return out


# --- log --------------------------------------------------------------------


def _ensure_log_header() -> None:
    if not LOG_FILE.exists() or LOG_FILE.stat().st_size == 0:
        with LOG_FILE.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(LOG_COLUMNS)


def log_action(*, action: str, prospect_email: str, classification: str = "",
               thread_id: str = "", note: str = "") -> None:
    _ensure_log_header()
    row = [
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
        action,
        prospect_email,
        classification,
        thread_id,
        note.replace("\n", " ")[:500],
    ]
    with LOG_FILE.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)
