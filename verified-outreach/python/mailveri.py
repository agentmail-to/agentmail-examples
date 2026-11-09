"""
Minimal MailVeri client + send policy.

Uses the single-address endpoint documented at https://mailveri.com/docs/:

    POST https://api.mailveri.com/v1/verify-mail/
    Authorization: Bearer <MAILVERI_API_KEY>
    {"email": "jane.doe@example.com"}

    -> {"error": 0, "status": "VALID", "email": "...", "balance": 999, "message": "..."}

`error` is 0 on success and 2 when the account is out of credits.
"""

import os
from dataclasses import dataclass

import httpx

DEFAULT_BASE_URL = "https://api.mailveri.com"

# Decisions the agent can make for a verified address.
SEND = "send"
SKIP = "skip"
REVIEW = "review"


class MailVeriError(Exception):
    """Any non-success response. `fatal` means stop the run (auth / credits)."""

    def __init__(self, message: str, fatal: bool = False):
        super().__init__(message)
        self.fatal = fatal


@dataclass
class Verification:
    email: str
    status: str  # VALID, INVALID, DISPOSABLE, ROLE_ACCOUNT, CATCH_ALL, FULL_INBOX, UNKNOWN
    balance: int | None
    message: str


def verify(email: str, api_key: str, timeout: float = 30.0) -> Verification:
    base_url = os.getenv("MAILVERI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    try:
        resp = httpx.post(
            f"{base_url}/v1/verify-mail/",
            json={"email": email},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
    except httpx.HTTPError as e:
        raise MailVeriError(f"network error: {e}") from e

    if resp.status_code in (401, 403):
        raise MailVeriError("invalid or unauthorized MAILVERI_API_KEY", fatal=True)
    if resp.status_code == 429:
        raise MailVeriError("rate limited (1 request/second for single verify)")

    try:
        data = resp.json()
    except ValueError:
        raise MailVeriError(f"non-JSON response (HTTP {resp.status_code})") from None

    error = data.get("error", 0)
    if error == 2:
        raise MailVeriError(data.get("message") or "not enough credits", fatal=True)
    if error != 0:
        raise MailVeriError(data.get("message") or f"verification failed (error={error})")

    return Verification(
        email=data.get("email") or data.get("mail") or email,
        status=(data.get("status") or "UNKNOWN").upper(),
        balance=data.get("balance"),
        message=data.get("message", ""),
    )


def decide(status: str, send_role_accounts: bool = False, send_catch_all: bool = False) -> str:
    """Map a MailVeri status to send / skip / review.

    - VALID: send.
    - INVALID, DISPOSABLE, FULL_INBOX: skip. Sending these only adds bounces.
    - ROLE_ACCOUNT: shared inboxes (info@, sales@). Deliverable, but cold
      outreach to them tends to get ignored or flagged. Review by default.
    - CATCH_ALL: the domain accepts everything, so the mailbox itself can't be
      confirmed. Review by default.
    - UNKNOWN (or anything new): the mail server didn't give a clear answer.
      Review, never send blind.
    """
    status = (status or "").upper()
    if status == "VALID":
        return SEND
    if status in ("INVALID", "DISPOSABLE", "FULL_INBOX"):
        return SKIP
    if status == "ROLE_ACCOUNT":
        return SEND if send_role_accounts else REVIEW
    if status == "CATCH_ALL":
        return SEND if send_catch_all else REVIEW
    return REVIEW
