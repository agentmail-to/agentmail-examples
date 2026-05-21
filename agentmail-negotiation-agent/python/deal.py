"""
JSON-backed deal state.

`deal.json` schema:
  {
    "what": "...",                      # what's being negotiated
    "must_haves": ["...", "..."],
    "ideal_price": 36000,
    "max_price": 39500,
    "currency": "USD",
    "deal_context": "...",              # free-text extra info (trade-in, financing, deadlines)
    "counterparties": [
      {
        "email": "...",
        "name": "...",
        "status": "queued|contacted|offered|declined|countered|target_hit|walked",
        "thread_id": "...",
        "current_offer": {              # populated by record_offer
          "price": 35000,
          "currency": "USD",
          "terms_summary": "...",
          "meets_must_haves": true,
          "notes": "..."
        }
      }
    ]
  }

`buyer_email` and `buyer_thread_id` get added at runtime when the agent first
contacts the buyer (so we can route the round summary back to the same thread).
"""

import json
from pathlib import Path

DEAL_FILE = Path("deal.json")


def load() -> dict:
    if not DEAL_FILE.exists():
        return {}
    try:
        return json.loads(DEAL_FILE.read_text())
    except Exception:
        return {}


def save(state: dict) -> None:
    DEAL_FILE.write_text(json.dumps(state, indent=2))


def get_counterparty_by_email(email: str) -> dict | None:
    deal = load()
    for cp in deal.get("counterparties", []):
        if cp.get("email", "").lower() == email.lower():
            return cp
    return None


def get_counterparty_by_thread(thread_id: str) -> dict | None:
    deal = load()
    for cp in deal.get("counterparties", []):
        if cp.get("thread_id") == thread_id:
            return cp
    return None


def update_counterparty(email: str, **fields) -> dict | None:
    deal = load()
    target = None
    for cp in deal.get("counterparties", []):
        if cp.get("email", "").lower() == email.lower():
            cp.update(fields)
            target = cp
            break
    if target:
        save(deal)
    return target


def queued_counterparties() -> list[dict]:
    deal = load()
    return [
        cp for cp in deal.get("counterparties", [])
        if cp.get("status", "queued") in ("", "queued")
    ]


def all_replied(deal_state: dict | None = None) -> bool:
    """True if every counterparty has either offered, declined, or walked."""
    deal = deal_state or load()
    cps = deal.get("counterparties", [])
    if not cps:
        return False
    terminal = {"offered", "declined", "walked", "target_hit"}
    return all(cp.get("status") in terminal for cp in cps)
