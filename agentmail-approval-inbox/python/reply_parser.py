"""
Parse the user's one-line reply on a request thread.

Decisions: approve / decline / defer N / changes
"""

import re

APPROVE_KEYWORDS = {
    "approve", "approved", "yes", "y", "ship", "ok", "okay", "go", "lgtm",
    "✅", "👍", "send it", "do it", "accept", "confirm",
}

DECLINE_KEYWORDS = {
    "decline", "declined", "deny", "denied", "no", "n", "reject", "rejected",
    "kill", "block", "stop", "❌", "👎", "abort",
}

DEFER_RE = re.compile(
    r"^(defer|snooze|wait|hold|pause|later)\s*(?:by\s*)?(\d+)\s*(d|day|days|w|wk|wks|week|weeks|h|hr|hrs|hour|hours)?",
    re.I,
)

CHANGES_RE = re.compile(
    r"^(?:request\s+changes|edit|revise|change|modify|amend)\s*[:\-]?\s*(.*)",
    re.I | re.S,
)

DECLINE_WITH_REASON_RE = re.compile(
    r"^(?:decline|reject|no|deny)\s*[:\-]\s*(.+)",
    re.I | re.S,
)


def parse(text: str) -> dict:
    """Returns {decision, ...optional fields}.

    decision: 'approve' | 'decline' | 'defer' | 'changes' | 'unknown'
    For decline: reason (str)
    For defer:   days (int) — hours collapsed into days/24 with min 1
    For changes: changes_text (str)
    """
    if not text:
        return {"decision": "unknown"}

    first_line = text.strip().splitlines()[0].strip().lower()
    # Strip trailing punctuation
    first_line = re.sub(r"[.!?\s]+$", "", first_line)

    # Decline with reason: "decline: too high"
    m = DECLINE_WITH_REASON_RE.match(first_line)
    if m:
        return {"decision": "decline", "reason": m.group(1).strip()}

    # Defer N units
    m = DEFER_RE.match(first_line)
    if m:
        n = int(m.group(2))
        unit = (m.group(3) or "d").lower()
        if unit.startswith("h"):
            days = max(1, n // 24)
        elif unit.startswith("w"):
            days = n * 7
        else:
            days = n
        return {"decision": "defer", "days": days}

    # Request changes: "edit: change date to May 12"
    m = CHANGES_RE.match(first_line)
    if m:
        return {"decision": "changes", "changes_text": m.group(1).strip()}

    if first_line in APPROVE_KEYWORDS:
        return {"decision": "approve"}

    if first_line in DECLINE_KEYWORDS:
        return {"decision": "decline", "reason": ""}

    # Common multi-word approve forms not in the set above
    if any(first_line.startswith(p) for p in ("approve ", "accept ", "ship ", "go ahead")):
        return {"decision": "approve"}

    return {"decision": "unknown"}
