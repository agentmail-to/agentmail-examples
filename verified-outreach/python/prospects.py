"""
CSV-backed prospect list + verify_log.csv audit log.

prospects.csv columns (header row required):
  email, name, company, hook, status, verify_status, verified_at, sent_at, thread_id

`status` moves through:
  queued -> sent | skipped | needs_review | dry_run
Rows with status empty or 'queued' are picked up on the next run. To retry a
row (for example after reviewing a CATCH_ALL), set its status back to 'queued'.
"""

import csv
from datetime import datetime, timezone
from pathlib import Path

PROSPECTS_FILE = Path("prospects.csv")
LOG_FILE = Path("verify_log.csv")

COLUMNS = [
    "email", "name", "company", "hook",
    "status", "verify_status", "verified_at", "sent_at", "thread_id",
]

LOG_COLUMNS = [
    "timestamp_utc", "email", "mailveri_status", "decision", "thread_id", "note",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_all() -> list[dict]:
    if not PROSPECTS_FILE.exists():
        return []
    with PROSPECTS_FILE.open(newline="", encoding="utf-8") as f:
        return [{c: (r.get(c) or "").strip() for c in COLUMNS} for r in csv.DictReader(f)]


def save_all(rows: list[dict]) -> None:
    with PROSPECTS_FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})


def update_prospect(email: str, **fields) -> None:
    rows = load_all()
    for r in rows:
        if r["email"].lower() == email.lower():
            r.update(fields)
            break
    save_all(rows)


def queued_prospects() -> list[dict]:
    return [r for r in load_all() if r["status"] in ("", "queued") and r["email"]]


def log(*, email: str, mailveri_status: str, decision: str,
        thread_id: str = "", note: str = "") -> None:
    new_file = not LOG_FILE.exists() or LOG_FILE.stat().st_size == 0
    with LOG_FILE.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(LOG_COLUMNS)
        w.writerow([now_iso(), email, mailveri_status, decision, thread_id,
                    note.replace("\n", " ")[:500]])
