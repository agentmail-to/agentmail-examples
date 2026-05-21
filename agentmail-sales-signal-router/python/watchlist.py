"""
Watchlist loader — re-reads watchlist.json on every call so live edits take
effect without restarting the agent.
"""

import json
from pathlib import Path

WATCHLIST_FILE = Path("watchlist.json")


def load() -> dict:
    if not WATCHLIST_FILE.exists():
        return {
            "deal_owners": {},
            "watchlist_domains": [],
            "watchlist_keywords": [],
            "crm_notification_senders": [],
        }
    try:
        return json.loads(WATCHLIST_FILE.read_text())
    except Exception as e:
        print(f"  ! watchlist.json malformed: {e}")
        return {
            "deal_owners": {},
            "watchlist_domains": [],
            "watchlist_keywords": [],
            "crm_notification_senders": [],
        }


def context_block(wl: dict) -> str:
    """Render the watchlist as a readable block to inject into the user message."""
    domains = wl.get("watchlist_domains", []) or []
    keywords = wl.get("watchlist_keywords", []) or []
    senders = wl.get("crm_notification_senders", []) or []
    return (
        f"Watchlist domains: {', '.join(domains) if domains else '(none)'}\n"
        f"Watchlist keywords: {', '.join(keywords) if keywords else '(none)'}\n"
        f"Known CRM/billing notification senders: {', '.join(senders) if senders else '(none)'}"
    )


def find_owner(wl: dict, sender_email: str, body_text: str) -> str:
    """Return Slack member ID for the rep who owns this domain, or empty string."""
    owners = wl.get("deal_owners", {}) or {}
    domain = sender_email.split("@", 1)[-1].lower() if "@" in sender_email else ""
    if domain and domain in owners:
        return owners[domain]
    # Also check if any owned domain is mentioned in the body (e.g. forwarded thread)
    body_lower = body_text.lower()
    for d, owner in owners.items():
        if d == "_comment":
            continue
        if d.lower() in body_lower:
            return owner
    return ""
