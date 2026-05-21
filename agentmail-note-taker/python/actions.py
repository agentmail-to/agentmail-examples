"""
actions.csv — flat ledger of all action items extracted across notes.

Columns:
  id, note_path, owner, task, deadline, urgency, status, created

`id` is a stable per-row hash so we can update status / dedup reminders.
`status` is one of: open, done, snoozed.
"""

import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path

ACTIONS_FILE = Path("actions.csv")
HEADER = ["id", "note_path", "owner", "task", "deadline", "urgency", "status", "created"]


def _ensure_header() -> None:
    if not ACTIONS_FILE.exists():
        with ACTIONS_FILE.open("w", newline="") as f:
            csv.writer(f).writerow(HEADER)


def _action_id(note_path: str, owner: str, task: str) -> str:
    return hashlib.sha1(f"{note_path}|{owner}|{task}".encode()).hexdigest()[:12]


def _read_all() -> list[dict]:
    if not ACTIONS_FILE.exists():
        return []
    with ACTIONS_FILE.open("r", newline="") as f:
        return list(csv.DictReader(f))


def _write_all(rows: list[dict]) -> None:
    _ensure_header()
    with ACTIONS_FILE.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in HEADER})


def append_from_note(note_path: str, action_items: list[dict]) -> list[dict]:
    """Append actions; skip duplicates (same note_path + owner + task).
    Returns the list of newly-added rows (with ids assigned)."""
    _ensure_header()
    existing = _read_all()
    existing_ids = {r["id"] for r in existing}

    new_rows: list[dict] = []
    for ai in action_items:
        owner = (ai.get("owner") or "").strip()
        task = (ai.get("task") or "").strip()
        if not task:
            continue
        aid = _action_id(note_path, owner, task)
        if aid in existing_ids:
            continue
        row = {
            "id": aid,
            "note_path": note_path,
            "owner": owner,
            "task": task,
            "deadline": (ai.get("deadline") or "").strip(),
            "urgency": (ai.get("urgency") or "").strip(),
            "status": "open",
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        new_rows.append(row)
        existing_ids.add(aid)

    if new_rows:
        with ACTIONS_FILE.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=HEADER)
            for r in new_rows:
                w.writerow(r)
    return new_rows


def mark_done_for_note(note_path: str) -> int:
    """Mark all open actions for the given note as done. Return count."""
    rows = _read_all()
    n = 0
    for r in rows:
        if r["note_path"] == note_path and r["status"] == "open":
            r["status"] = "done"
            n += 1
    if n:
        _write_all(rows)
    return n


def list_open() -> list[dict]:
    return [r for r in _read_all() if r["status"] == "open"]


def list_for_note(note_path: str) -> list[dict]:
    return [r for r in _read_all() if r["note_path"] == note_path]


def is_overdue(row: dict, today: datetime) -> bool:
    if not row.get("deadline"):
        return False
    try:
        d = datetime.fromisoformat(row["deadline"]).date()
    except Exception:
        return False
    return d < today.date()


def hours_until(row: dict, now: datetime) -> float | None:
    if not row.get("deadline"):
        return None
    try:
        d = datetime.fromisoformat(row["deadline"])
        # Treat date-only deadlines as end-of-day
        if d.time().hour == 0 and d.time().minute == 0:
            d = d.replace(hour=23, minute=59)
    except Exception:
        return None
    return (d - now.replace(tzinfo=None)).total_seconds() / 3600.0
