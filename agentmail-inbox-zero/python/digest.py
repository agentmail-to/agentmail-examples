"""
Build and send the morning digest.

Runs once per day from the polling loop in agent.py. Lists every draft created
since the previous digest, plus anything flagged for human attention.
"""

from datetime import datetime, timezone
from typing import List


def build_digest_text(
    user_name: str,
    drafts: List,
    flagged: List,
    inbox_email: str,
) -> str:
    """Format a plain-text digest email body."""
    today = datetime.now().strftime("%A, %B %d")

    lines = [
        f"Good morning {user_name},",
        "",
        f"Here's what landed overnight in {inbox_email}.",
        "",
    ]

    if drafts:
        lines.append(f"📝 {len(drafts)} DRAFT{'S' if len(drafts) != 1 else ''} READY TO REVIEW")
        lines.append("")
        for d in drafts:
            to = ", ".join(d.to) if d.to else "(no recipient)"
            subject = d.subject or "(no subject)"
            preview = (d.preview or d.text or "").strip().replace("\n", " ")[:140]
            lines.append(f"  → To: {to}")
            lines.append(f"    Subject: {subject}")
            lines.append(f"    Preview: {preview}{'...' if len(preview) >= 140 else ''}")
            lines.append("")
    else:
        lines.append("📝 No drafts to review.")
        lines.append("")

    if flagged:
        lines.append(f"⚠️  {len(flagged)} EMAIL{'S' if len(flagged) != 1 else ''} FLAGGED FOR YOUR ATTENTION")
        lines.append("")
        for m in flagged:
            sender = getattr(m, "from_", None) or getattr(m, "from", "")
            subject = m.subject or "(no subject)"
            lines.append(f"  → From: {sender}")
            lines.append(f"    Subject: {subject}")
            lines.append("")

    if not drafts and not flagged:
        lines.append("Inbox is clean. Nothing requires your attention.")
        lines.append("")

    lines.append("---")
    lines.append(f"Digest generated {today}. Open {inbox_email} to review and send.")

    return "\n".join(lines)


def is_digest_due(wake_time_str: str, last_digest_date: str | None) -> bool:
    """Return True if it's past WAKE_TIME today AND we haven't sent today's digest yet.

    wake_time_str: "HH:MM" (24h). last_digest_date: "YYYY-MM-DD" or None.
    """
    try:
        wh, wm = wake_time_str.strip().split(":")
        wake_h, wake_m = int(wh), int(wm)
    except Exception:
        wake_h, wake_m = 8, 0

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    if last_digest_date == today_str:
        return False  # already sent today

    # Has the wake time passed today?
    return (now.hour, now.minute) >= (wake_h, wake_m)
