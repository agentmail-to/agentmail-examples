"""
Lightweight CSV ticket log.

Appends one row per agent action. Lets the support manager grep, sort, or
import to a spreadsheet without standing up a database.

Columns: timestamp_utc, action, classification, sender, subject, message_id,
         thread_id, note
"""

import csv
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path("tickets.csv")

COLUMNS = [
    "timestamp_utc",
    "action",
    "classification",
    "sender",
    "subject",
    "message_id",
    "thread_id",
    "note",
]


def _ensure_header() -> None:
    if not LOG_FILE.exists() or LOG_FILE.stat().st_size == 0:
        with LOG_FILE.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(COLUMNS)


def log_ticket(
    *,
    action: str,                # responded | escalated | closed | followed_up
    classification: str,        # billing | bug | feature_request | general | urgent
    sender: str,
    subject: str,
    message_id: str,
    thread_id: str,
    note: str = "",
) -> None:
    _ensure_header()
    row = [
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
        action,
        classification,
        sender,
        (subject or "").replace("\n", " ")[:200],
        message_id,
        thread_id,
        note.replace("\n", " ")[:500],
    ]
    with LOG_FILE.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)
