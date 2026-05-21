"""
Build and send the daily digest.

Once per day at DIGEST_TIME, take the cached items from the last 24h, ask
Claude to dedupe + rank against USER_INTERESTS + format, and email the result
to USER_EMAIL.
"""

import json
import os
from datetime import datetime, timezone

from newsletter_cache import get_recent_items, clear_recent
from prompt import build_digest_prompt


COMPOSE_DIGEST_TOOL = {
    "name": "compose_digest",
    "description": (
        "Call this with the final, formatted digest email body. Should include "
        "a greeting, top 5-8 deduped + ranked items with links, and a signoff."
    ),
    "input_schema": {
        "type": "object",
        "required": ["body", "subject"],
        "properties": {
            "subject": {
                "type": "string",
                "description": "Email subject line. Keep it short and dated.",
            },
            "body": {
                "type": "string",
                "description": "The plain-text digest body in the format described in the system prompt.",
            },
        },
    },
}

SKIP_DIGEST_TOOL = {
    "name": "skip_digest",
    "description": "Call this when there's nothing worth digesting (no items in the last 24h, or all items are irrelevant). No email will be sent.",
    "input_schema": {
        "type": "object",
        "required": ["reason"],
        "properties": {
            "reason": {"type": "string"},
        },
    },
}


def _items_as_user_message(items: list[dict]) -> str:
    """Format the cached items as a JSON blob for Claude to rank/format."""
    return (
        f"Here are {len(items)} newsletter items collected over the last 24 hours:\n\n"
        f"```json\n{json.dumps(items, indent=2)}\n```\n\n"
        f"Compose the digest now."
    )


def is_digest_due(digest_time_str: str, last_digest_date: str | None) -> bool:
    """Past DIGEST_TIME today AND haven't sent today's digest yet."""
    try:
        wh, wm = digest_time_str.strip().split(":")
        wake_h, wake_m = int(wh), int(wm)
    except Exception:
        wake_h, wake_m = 8, 0
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    if last_digest_date == today_str:
        return False
    return (now.hour, now.minute) >= (wake_h, wake_m)


def send_digest(claude, agentmail, inbox, model: str, user_email: str) -> dict:
    """Build the digest and send it. Returns {sent: bool, item_count: int, reason?: str}."""
    items = get_recent_items(hours=24)
    if not items:
        return {"sent": False, "item_count": 0, "reason": "no items in last 24h"}

    print(f"  📊 Building digest from {len(items)} item(s)…")
    response = claude.messages.create(
        model=model,
        max_tokens=4096,
        system=build_digest_prompt(),
        tools=[COMPOSE_DIGEST_TOOL, SKIP_DIGEST_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": _items_as_user_message(items)}],
    )

    for block in response.content:
        if block.type != "tool_use":
            continue
        if block.name == "skip_digest":
            return {"sent": False, "item_count": len(items), "reason": block.input.get("reason", "")}
        if block.name == "compose_digest":
            subject = block.input.get("subject") or f"Newsletter digest — {datetime.now().strftime('%A, %B %d')}"
            body = block.input.get("body") or "(empty body)"
            print(f"  📨 Sending digest to {user_email} ({len(body)} chars)…")
            agentmail.inboxes.messages.send(
                inbox_id=inbox.inbox_id,
                to=[user_email],
                subject=subject,
                text=body,
            )
            clear_recent(items)
            return {"sent": True, "item_count": len(items)}

    return {"sent": False, "item_count": len(items), "reason": "Claude did not call any tool"}
