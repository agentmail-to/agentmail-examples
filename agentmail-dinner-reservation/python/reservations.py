"""
JSON-backed state for tracking active reservation requests.

Each reservation is keyed by the user's request thread_id and stores both the
user-side and restaurant-side thread metadata so we can route replies between them.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path("reservations.json")


def _load() -> dict:
    if not STATE_FILE.exists():
        return {"reservations": {}}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"reservations": {}}


def _save(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def upsert(reservation_id: str, **fields) -> dict:
    """Create or update a reservation record. Returns the updated record."""
    state = _load()
    rec = state["reservations"].setdefault(reservation_id, {
        "id": reservation_id,
        "status": "new",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    rec.update(fields)
    rec["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save(state)
    return rec


def get(reservation_id: str) -> dict | None:
    return _load()["reservations"].get(reservation_id)


def find_by_restaurant_thread(thread_id: str) -> dict | None:
    """Match an inbound reply to its reservation by the restaurant_thread_id."""
    state = _load()
    for rec in state["reservations"].values():
        if rec.get("restaurant_thread_id") == thread_id:
            return rec
    return None


def find_by_user_thread(thread_id: str) -> dict | None:
    state = _load()
    for rec in state["reservations"].values():
        if rec.get("user_thread_id") == thread_id:
            return rec
    return None


def all_reservations() -> list[dict]:
    return list(_load()["reservations"].values())
