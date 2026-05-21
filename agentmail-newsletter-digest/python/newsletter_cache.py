"""
JSON-backed cache of summarized newsletter items.

Schema: { "items": [ {date_iso, headline, key_points, primary_link, topic, importance, source_subject, source_from} ] }

Trim items older than RETENTION_DAYS so the file doesn't grow forever.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

CACHE_FILE = Path("newsletter_cache.json")
RETENTION_DAYS = 14


def _load() -> dict:
    if not CACHE_FILE.exists():
        return {"items": []}
    try:
        return json.loads(CACHE_FILE.read_text())
    except Exception:
        return {"items": []}


def _save(state: dict) -> None:
    CACHE_FILE.write_text(json.dumps(state, indent=2))


def _trim(state: dict) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    state["items"] = [
        i for i in state.get("items", [])
        if datetime.fromisoformat(i["date_iso"]) >= cutoff
    ]


def append_item(item: dict) -> None:
    state = _load()
    state["items"].append(item)
    _trim(state)
    _save(state)


def get_recent_items(hours: int = 24) -> list[dict]:
    """Return items added in the last N hours."""
    state = _load()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return [
        i for i in state.get("items", [])
        if datetime.fromisoformat(i["date_iso"]) >= cutoff
    ]


def clear_recent(items: list[dict]) -> None:
    """Mark these items as 'sent' by removing them from the cache.
    Use after a successful digest send so they don't appear in the next one."""
    state = _load()
    item_ids = {i.get("source_message_id") for i in items}
    state["items"] = [
        i for i in state.get("items", [])
        if i.get("source_message_id") not in item_ids
    ]
    _save(state)
