"""
requests.csv — append-only ledger of every classified request.

Schema:
  id, thread_id, type, status, summary, fields_json,
  source_message_id, source_sender, created, decided_at, decided_text
"""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

FILE = Path("requests.csv")
HEADER = [
    "id", "thread_id", "type", "status", "summary", "fields_json",
    "source_message_id", "source_sender", "created", "decided_at", "decided_text",
]


def _ensure_header() -> None:
    if not FILE.exists():
        with FILE.open("w", newline="") as f:
            csv.writer(f).writerow(HEADER)


def _request_id(thread_id: str, source_message_id: str) -> str:
    return hashlib.sha1(f"{thread_id}|{source_message_id}".encode()).hexdigest()[:12]


def _read_all() -> list[dict]:
    if not FILE.exists():
        return []
    with FILE.open("r", newline="") as f:
        return list(csv.DictReader(f))


def _write_all(rows: list[dict]) -> None:
    _ensure_header()
    with FILE.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in HEADER})


def append(*, thread_id: str, type_name: str, summary: str, fields: dict,
           source_message_id: str, source_sender: str) -> dict:
    _ensure_header()
    row = {
        "id": _request_id(thread_id, source_message_id),
        "thread_id": thread_id,
        "type": type_name,
        "status": "pending",
        "summary": summary,
        "fields_json": json.dumps(fields),
        "source_message_id": source_message_id,
        "source_sender": source_sender,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decided_at": "",
        "decided_text": "",
    }
    with FILE.open("a", newline="") as f:
        csv.DictWriter(f, fieldnames=HEADER).writerow(row)
    return row


def find_pending_by_thread(thread_id: str) -> dict | None:
    if not thread_id:
        return None
    for r in reversed(_read_all()):  # most recent first
        if r["thread_id"] == thread_id and r["status"] == "pending":
            return r
    return None


def update_status(request_id: str, new_status: str, decided_text: str = "") -> bool:
    rows = _read_all()
    n = 0
    for r in rows:
        if r["id"] == request_id:
            r["status"] = new_status
            r["decided_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            r["decided_text"] = decided_text
            n += 1
    if n:
        _write_all(rows)
    return n > 0


def stats() -> dict:
    counts = {"pending": 0, "approved": 0, "declined": 0, "deferred": 0, "changes_requested": 0}
    for r in _read_all():
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return counts
