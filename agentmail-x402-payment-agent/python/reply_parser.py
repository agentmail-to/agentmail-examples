"""
Parse the user's reply on a needs_review payment thread.

Decisions: approve / decline / unknown
"""

import re

APPROVE_KEYWORDS = {
    "approve", "approved", "yes", "y", "pay", "ship", "ok", "okay", "go", "lgtm",
    "✅", "👍", "send it", "do it", "confirm", "authorize", "authorise",
}

DECLINE_KEYWORDS = {
    "decline", "declined", "deny", "denied", "no", "n", "reject", "rejected",
    "kill", "block", "stop", "❌", "👎", "abort", "skip",
}

DECLINE_WITH_REASON_RE = re.compile(
    r"^(?:decline|reject|no|deny|skip)\s*[:\-]\s*(.+)",
    re.I | re.S,
)


def parse(text: str) -> dict:
    if not text:
        return {"decision": "unknown"}
    first = text.strip().splitlines()[0].strip().lower() if text.strip() else ""
    first = re.sub(r"[.!?\s]+$", "", first)

    m = DECLINE_WITH_REASON_RE.match(first)
    if m:
        return {"decision": "decline", "reason": m.group(1).strip()}

    if first in APPROVE_KEYWORDS:
        return {"decision": "approve"}
    if first in DECLINE_KEYWORDS:
        return {"decision": "decline", "reason": ""}
    if any(first.startswith(p) for p in ("approve ", "pay ", "authorize ", "authorise ")):
        return {"decision": "approve"}
    return {"decision": "unknown"}
