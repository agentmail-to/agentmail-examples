"""
AgentMail Verified Outreach - verify every prospect with MailVeri before the
agent sends the first touch.

Workflow:
  1. Read queued prospects from prospects.csv.
  2. Verify each address with MailVeri (1 request/second).
  3. Decide: VALID -> send, INVALID / DISPOSABLE / FULL_INBOX -> skip,
     ROLE_ACCOUNT / CATCH_ALL / UNKNOWN -> hold for review (configurable).
  4. Send the first touch from an AgentMail inbox, labelled with the result.
  5. Write every decision to prospects.csv and verify_log.csv.

Run:
    pip install -r requirements.txt
    cp .env.example .env
    cp prospects.example.csv prospects.csv  # edit this with your real prospects
    python agent.py
"""

import json
import os
import time
from pathlib import Path

from agentmail import AgentMail
from agentmail.inboxes import CreateInboxRequest
from dotenv import load_dotenv

import mailveri
import prospects

load_dotenv()

# --- config -------------------------------------------------------------------


def _flag(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in ("1", "true", "yes")


AGENTMAIL_API_KEY = os.environ["AGENTMAIL_API_KEY"]
MAILVERI_API_KEY = os.environ["MAILVERI_API_KEY"]
SENDER_NAME = os.getenv("SENDER_NAME", "Sender")
SENDER_COMPANY = os.getenv("SENDER_COMPANY", "Company")
SEND_ROLE_ACCOUNTS = _flag("SEND_ROLE_ACCOUNTS")
SEND_CATCH_ALL = _flag("SEND_CATCH_ALL")
DRY_RUN = _flag("DRY_RUN")
VERIFY_INTERVAL = float(os.getenv("VERIFY_INTERVAL_SECONDS", "1.1"))
INBOX_USERNAME = os.getenv("INBOX_USERNAME") or None

STATE_FILE = Path(".agent_state.json")

agentmail = AgentMail(api_key=AGENTMAIL_API_KEY)


# --- inbox --------------------------------------------------------------------


def get_or_create_inbox():
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    if state.get("inbox_id"):
        try:
            return agentmail.inboxes.get(state["inbox_id"])
        except Exception as e:
            print(f"(stale state, creating new inbox: {e})")

    inbox = agentmail.inboxes.create(
        request=CreateInboxRequest(
            username=INBOX_USERNAME,
            display_name=f"{SENDER_NAME} - {SENDER_COMPANY}",
        )
    )
    STATE_FILE.write_text(json.dumps({"inbox_id": inbox.inbox_id, "email": inbox.email}, indent=2))
    return inbox


# --- message ------------------------------------------------------------------
# A plain template keeps this example focused on the verification gate. To use
# an LLM writer instead, swap in write_email_body() from ../../gtm-agent.


def compose(prospect: dict) -> tuple[str, str]:
    first = (prospect["name"].split() or ["there"])[0]
    subject = f"Quick question about {prospect['company']}" if prospect["company"] else "Quick question"
    body = (
        f"Hi {first},\n\n"
        f"Saw that {prospect['hook'].rstrip('.')}. "
        f"Would a 15-minute call next week be useful?\n\n"
        f"{SENDER_NAME}\n{SENDER_COMPANY}"
    )
    return subject, body


# --- verification gate --------------------------------------------------------


def verify_with_retry(email: str) -> mailveri.Verification:
    try:
        return mailveri.verify(email, MAILVERI_API_KEY)
    except mailveri.MailVeriError as e:
        if e.fatal:
            raise
        print(f"    ! {e}, retrying once")
        time.sleep(2)
        return mailveri.verify(email, MAILVERI_API_KEY)


def process(prospect: dict, inbox) -> None:
    email = prospect["email"]
    print(f"\n🔎 {email}")

    try:
        result = verify_with_retry(email)
    except mailveri.MailVeriError as e:
        if e.fatal:
            raise
        # Leave the row queued so the next run tries again. Never send unverified.
        print(f"    ! verification failed, left queued: {e}")
        prospects.log(email=email, mailveri_status="ERROR", decision="retry_later", note=str(e))
        return

    decision = mailveri.decide(result.status, SEND_ROLE_ACCOUNTS, SEND_CATCH_ALL)
    print(f"    MailVeri: {result.status} -> {decision} (credits left: {result.balance})")
    prospects.update_prospect(email, verify_status=result.status, verified_at=prospects.now_iso())

    if decision == mailveri.SKIP:
        prospects.update_prospect(email, status="skipped")
        prospects.log(email=email, mailveri_status=result.status, decision="skipped")
        return
    if decision == mailveri.REVIEW:
        prospects.update_prospect(email, status="needs_review")
        prospects.log(email=email, mailveri_status=result.status, decision="needs_review",
                      note="set status back to 'queued' to send after review")
        return

    subject, body = compose(prospect)
    if DRY_RUN:
        print(f"    (dry run) would send: {subject}")
        prospects.update_prospect(email, status="dry_run")
        prospects.log(email=email, mailveri_status=result.status, decision="dry_run", note=subject)
        return

    sent = agentmail.inboxes.messages.send(
        inbox.inbox_id,
        to=[email],
        subject=subject,
        text=body,
        labels=["outreach", f"mailveri-{result.status.lower().replace('_', '-')}"],
    )
    print(f"    ✉  sent (thread {sent.thread_id})")
    prospects.update_prospect(email, status="sent", sent_at=prospects.now_iso(), thread_id=sent.thread_id)
    prospects.log(email=email, mailveri_status=result.status, decision="sent",
                  thread_id=sent.thread_id, note=subject)


# --- main ---------------------------------------------------------------------


def main():
    queue = prospects.queued_prospects()
    if not queue:
        print("No queued prospects in prospects.csv.")
        return

    inbox = None if DRY_RUN else get_or_create_inbox()
    print(f"📬 Sending from: {inbox.email if inbox else '(dry run, nothing will be sent)'}")
    print(f"   {len(queue)} queued | role accounts: {'send' if SEND_ROLE_ACCOUNTS else 'review'}"
          f" | catch-all: {'send' if SEND_CATCH_ALL else 'review'}")

    for i, p in enumerate(queue):
        if i:
            time.sleep(VERIFY_INTERVAL)
        try:
            process(p, inbox)
        except mailveri.MailVeriError as e:
            print(f"\n✋ Stopping: {e}. Remaining prospects stay queued.")
            return
        except Exception as e:
            print(f"    ! failed for {p['email']}: {e}")

    print("\nDone. See prospects.csv for status and verify_log.csv for the audit log.")


if __name__ == "__main__":
    main()
