"""
End-of-day digest: groups today's signals.csv rows by classification and
sends a summary via (a) email to SALES_LEAD_EMAIL and (b) Slack.

Fires once per day around DIGEST_HOUR (local time). The .last_digest
state file dedupes against re-runs / restarts.
"""

import os
from datetime import datetime
from pathlib import Path

import signals as signals_mod
import slack as slack_mod


STATE = Path(".last_digest")


def _already_sent_today() -> bool:
    if not STATE.exists():
        return False
    return STATE.read_text().strip() == datetime.now().strftime("%Y-%m-%d")


def _mark_sent_today() -> None:
    STATE.write_text(datetime.now().strftime("%Y-%m-%d"))


def _build_digest_text(rows: list[dict]) -> str:
    if not rows:
        return f":calendar: *EOD signals digest* — no signals today."

    by_class: dict[str, list[dict]] = {}
    for r in rows:
        by_class.setdefault(r["classification"], []).append(r)

    hot = by_class.get("hot_reply", [])
    crm = by_class.get("crm_notification", [])
    watch = by_class.get("watchlist_match", [])
    noise = by_class.get("noise", [])

    total_amount = sum(float(r.get("amount_usd") or 0) for r in crm)

    lines = [
        f":calendar: *EOD signals digest* — {datetime.now().strftime('%A, %b %d')}",
        "",
        f"• Hot replies: {len(hot)}   • CRM events: {len(crm)}   "
        f"• Watchlist hits: {len(watch)}   • Noise: {len(noise)}",
    ]
    if total_amount:
        lines.append(f"• Total deal volume from CRM events: ${total_amount:,.0f}")

    if hot:
        lines += ["", "*Top hot replies:*"]
        # Prioritize positive intent, then objections, then others
        priority = {"positive": 0, "objection": 1, "unsubscribe": 2, "ooo": 3}
        hot_sorted = sorted(hot, key=lambda r: priority.get(r.get("sentiment_or_event", ""), 9))
        for r in hot_sorted[:5]:
            lines.append(f"  • [{r.get('sentiment_or_event', '?')}] {r.get('sender', '')} — {r.get('summary', '')}")

    if crm:
        lines += ["", "*CRM events:*"]
        for r in sorted(crm, key=lambda r: float(r.get("amount_usd") or 0), reverse=True)[:5]:
            amt = float(r.get("amount_usd") or 0)
            amt_str = f"${amt:,.0f}" if amt else ""
            lines.append(f"  • {r.get('sentiment_or_event', '')}: {r.get('customer', '')} {amt_str} — {r.get('summary', '')}")

    if watch:
        lines += ["", "*Watchlist hits:*"]
        for r in watch[:5]:
            lines.append(f"  • {r.get('sender', '')} ({r.get('sentiment_or_event', '')}) — {r.get('summary', '')}")

    return "\n".join(lines)


def maybe_send(*, agentmail_client, inbox, sales_lead_email: str, hour: int) -> None:
    """Call this once per agent loop iteration. Sends the digest at hour:00 (local) once per day."""
    now = datetime.now()
    if now.hour < hour:
        return
    if _already_sent_today():
        return

    rows = signals_mod.read_today()
    text = _build_digest_text(rows)

    # 1. Slack
    slack_mod.digest(blocks_text=text)
    print(f"  ✓ digest posted to Slack ({len(rows)} signals)")

    # 2. Email to sales lead
    if sales_lead_email:
        try:
            agentmail_client.inboxes.messages.send(
                inbox.inbox_id,
                to=[sales_lead_email],
                subject=f"[Sales signals] EOD digest — {now.strftime('%b %d')} — {len(rows)} signals",
                text=text,
            )
            print(f"  ✓ digest emailed to {sales_lead_email}")
        except Exception as e:
            print(f"  ! couldn't email digest: {e}")

    _mark_sent_today()
