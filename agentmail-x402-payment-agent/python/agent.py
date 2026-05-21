"""
AgentMail x402 Payment Agent — extract → validate → pay (or escalate).

Per incoming email, the agent does ONE of the following:

  A. Reply on a thread with a pending review → parse user's approve/decline,
     fire the payment if approved, log the decision, ack.

  B. New email — Claude calls EXACTLY ONE of:
       pay_now(vendor, amount, currency, invoice_url, ...)
         → if vendor on allowlist AND amount within cap AND not duplicate:
              fire payment via configured adapter, log to payments.csv,
              receipt to vendor + CC finance
            else:
              route to needs_review (over-limit / unknown vendor / dup)
       needs_review(reason, partial_fields)
         → save to payments.csv as pending_review, email user for sign-off
       discard(reason)
         → silently mark read

Adapter selection via .env PAYMENT_ADAPTER:
  mock     — built-in simulator that demonstrates the full x402 wire shape
  coinbase — real Coinbase CDP facilitator (requires CDP keys + wallet)

Run:
    pip install -r requirements.txt
    cp .env.example .env
    cp vendors.example.csv vendors.csv   # add your real allowlist
    python agent.py
"""

import importlib
import json
import os
import time
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path

from agentmail import AgentMail
from agentmail.inboxes import CreateInboxRequest
from anthropic import Anthropic
from dotenv import load_dotenv

import payments_store
import reply_parser
import vendors_store
from prompt import build_classify_prompt

load_dotenv()

# --- config -------------------------------------------------------------------

AGENTMAIL_API_KEY = os.environ["AGENTMAIL_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
COMPANY_NAME = os.getenv("COMPANY_NAME", "Acme")
USER_EMAIL = os.environ["USER_EMAIL"]
FINANCE_EMAIL = os.getenv("FINANCE_EMAIL", "")
GLOBAL_MAX_USD = float(os.getenv("GLOBAL_MAX_USD", "1000"))
PAYMENT_CURRENCY = os.getenv("PAYMENT_CURRENCY", "USDC")
PAYMENT_ADAPTER_NAME = os.getenv("PAYMENT_ADAPTER", "mock")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "15"))
INBOX_USERNAME = os.getenv("INBOX_USERNAME") or None

STATE_FILE = Path(".agent_state.json")

# --- clients ------------------------------------------------------------------

agentmail = AgentMail(api_key=AGENTMAIL_API_KEY)
claude = Anthropic(api_key=ANTHROPIC_API_KEY)

# --- payment adapter loader ---------------------------------------------------


def _load_adapter():
    if PAYMENT_ADAPTER_NAME not in {"mock", "coinbase"}:
        raise SystemExit(f"unknown PAYMENT_ADAPTER: {PAYMENT_ADAPTER_NAME!r} (use 'mock' or 'coinbase')")
    return importlib.import_module(f"{PAYMENT_ADAPTER_NAME}_adapter")


adapter = _load_adapter()
PaymentError = adapter.PaymentError if hasattr(adapter, "PaymentError") else Exception


# --- Claude tools -------------------------------------------------------------

PAY_NOW_TOOL = {
    "name": "pay_now",
    "description": "Email is a payment request from a known vendor with all required fields. Extract them. The agent will validate against the allowlist + cap BEFORE actually paying.",
    "input_schema": {
        "type": "object",
        "required": ["vendor_name", "vendor_email", "amount", "currency", "invoice_url", "summary"],
        "properties": {
            "vendor_name": {"type": "string"},
            "vendor_email": {"type": "string"},
            "amount": {"type": "number"},
            "currency": {"type": "string", "enum": ["USDC", "USD", "USDT", "ETH"]},
            "invoice_url": {"type": "string", "description": "x402 payment URL"},
            "invoice_number": {"type": "string"},
            "summary": {"type": "string"},
        },
    },
}

NEEDS_REVIEW_TOOL = {
    "name": "needs_review",
    "description": "Looks like a payment request but agent shouldn't fire pay_now (missing field, unfamiliar vendor, suspicious context).",
    "input_schema": {
        "type": "object",
        "required": ["reason", "summary"],
        "properties": {
            "reason": {"type": "string"},
            "partial_fields": {
                "type": "object",
                "description": "Extracted fields you DID get (use empty string for missing).",
                "additionalProperties": {"type": "string"},
            },
            "summary": {"type": "string"},
        },
    },
}

DISCARD_TOOL = {
    "name": "discard",
    "description": "Not a payment request — newsletter, marketing, internal, etc.",
    "input_schema": {
        "type": "object",
        "required": ["reason"],
        "properties": {"reason": {"type": "string"}},
    },
}

CLASSIFY_TOOLS = [PAY_NOW_TOOL, NEEDS_REVIEW_TOOL, DISCARD_TOOL]


# --- state --------------------------------------------------------------------


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


# --- helpers ------------------------------------------------------------------


def _sender_email(message) -> str:
    sender = getattr(message, "from_", None) or getattr(message, "from", None) or ""
    _, email = parseaddr(str(sender))
    return email.lower()


def get_or_create_inbox():
    state = load_state()
    if state.get("inbox_id"):
        try:
            return agentmail.inboxes.get(state["inbox_id"])
        except Exception as e:
            print(f"(stale state, creating new inbox: {e})")

    inbox = agentmail.inboxes.create(
        request=CreateInboxRequest(
            username=INBOX_USERNAME,
            display_name=f"{COMPANY_NAME} Pay Agent",
        )
    )
    state["inbox_id"] = inbox.inbox_id
    state["email"] = inbox.email
    save_state(state)
    return inbox


def _mark_read(inbox_id: str, message_id: str, add_labels=None) -> None:
    try:
        agentmail.inboxes.messages.update(
            inbox_id, message_id,
            remove_labels=["unread"],
            add_labels=add_labels,
        )
    except Exception as e:
        print(f"  ! couldn't mark read: {e}")


# --- core processing ----------------------------------------------------------


def process_message(message, inbox, vendors):
    full = agentmail.inboxes.messages.get(inbox.inbox_id, message.message_id)
    extracted = (getattr(full, "extracted_text", None) or "").strip()
    raw = (full.text or "").strip()
    body = raw if len(raw) > len(extracted) * 1.5 else (extracted or raw)

    sender = _sender_email(message)
    subject = getattr(message, "subject", "") or ""
    thread_id = getattr(full, "thread_id", "") or ""
    print(f"  → {sender}  ·  '{subject[:60]}'  ·  thread {thread_id[:24]}")

    if sender == inbox.email.lower():
        print("  · skipping our own outgoing reply")
        _mark_read(inbox.inbox_id, message.message_id)
        return

    # Is this a reply on a pending-review thread?
    # We track by source_message_id of the original payment request, but
    # threading lookups need to use the full thread context — find any pending
    # payment whose original message lives in this thread.
    pending = _find_pending_in_thread(thread_id)
    if pending:
        return _handle_review_reply(message, pending, body, inbox, vendors)

    # Else classify
    response = claude.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=build_classify_prompt(inbox.email),
        tools=CLASSIFY_TOOLS,
        tool_choice={"type": "any"},
        messages=[{
            "role": "user",
            "content": (
                f"From: {sender}\n"
                f"Subject: {subject}\n\n"
                f"{body[:8000] if body else '(empty body)'}"
            ),
        }],
    )

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if not tool_use:
        print("  ! Claude returned no tool call")
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["error"])
        return

    args = tool_use.input or {}
    print(f"  ✓ classification: {tool_use.name}  args: {json.dumps(args)[:200]}")

    if tool_use.name == "discard":
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["discarded"])
        return

    if tool_use.name == "needs_review":
        _route_to_review(message, args, inbox, sender,
                         reason=args.get("reason", "manual_review"))
        return

    # pay_now — validate, then either fire or route to review
    return _handle_pay_now(message, args, inbox, vendors, sender)


def _find_pending_in_thread(thread_id: str) -> dict | None:
    """Look up a pending payment whose original-source message is in this thread.
    We need to first enumerate the thread's messages to find which message_id
    matches a pending row in payments.csv."""
    if not thread_id:
        return None
    try:
        # Quickest: pull the thread, scan for messages whose ID is on a pending row
        # Fall back: linear scan of payments.csv if SDK doesn't support this
        # For simplicity here we just scan payments.csv — list size will be small
        # for individual users.
        import csv as _csv
        from pathlib import Path as _Path
        if not _Path("payments.csv").exists():
            return None
        rows = list(_csv.DictReader(open("payments.csv")))
        # Pending rows for this template are tagged by source_message_id; match any
        # message in the thread.
        try:
            messages_in_thread = agentmail.threads.get(thread_id).messages or []
            ids_in_thread = {m.message_id for m in messages_in_thread}
        except Exception:
            ids_in_thread = set()
        for r in reversed(rows):
            if r["status"] == "pending_review" and r["source_message_id"] in ids_in_thread:
                return r
        return None
    except Exception as e:
        print(f"  ! thread lookup failed: {e}")
        return None


def _handle_pay_now(message, args, inbox, vendors, sender):
    vendor_email = (args.get("vendor_email") or sender).lower()
    vendor_name = args.get("vendor_name") or vendor_email
    amount = float(args.get("amount") or 0)
    currency = args.get("currency") or PAYMENT_CURRENCY
    invoice_url = args.get("invoice_url") or ""
    invoice_number = args.get("invoice_number") or ""
    summary = args.get("summary", "")

    # 1. Duplicate check
    if invoice_number and payments_store.is_duplicate(invoice_number, vendor_email):
        print(f"  · duplicate invoice {invoice_number} from {vendor_email} — skipping")
        try:
            agentmail.inboxes.messages.reply(
                inbox.inbox_id, message.message_id,
                text=(
                    f"This invoice ({invoice_number}) was already received and processed. "
                    f"If this is in error, please contact {USER_EMAIL}.\n\n— {COMPANY_NAME} Pay Agent"
                ),
            )
        except Exception:
            pass
        payments_store.append(
            vendor_name=vendor_name, vendor_email=vendor_email, amount=amount,
            currency=currency, invoice_number=invoice_number,
            decision="duplicate", status="skipped",
            source_message_id=message.message_id,
        )
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["duplicate"])
        return

    # 2. Allowlist check
    vendor = vendors_store.find(vendors, vendor_email)
    if not vendor:
        print(f"  · {vendor_email} not on allowlist — routing to review")
        _route_to_review(message, args, inbox, sender,
                         reason="vendor_not_on_allowlist", row_amount=amount,
                         row_currency=currency, row_invoice=invoice_number)
        return

    # 3. Amount cap check (per-vendor + global)
    cap = min(vendor["max_amount_usd"], GLOBAL_MAX_USD)
    if amount > cap:
        print(f"  · ${amount:.2f} > cap ${cap:.2f} — routing to review")
        _route_to_review(message, args, inbox, sender,
                         reason=f"amount_${amount:.0f}_exceeds_cap_${cap:.0f}",
                         row_amount=amount, row_currency=currency,
                         row_invoice=invoice_number)
        return

    # 4. All clear — fire payment via the configured adapter
    print(f"  → AUTO-PAYING ${amount:.2f} {currency} to {vendor_name}")
    payment_row = payments_store.append(
        vendor_name=vendor_name, vendor_email=vendor_email, amount=amount,
        currency=currency, invoice_number=invoice_number,
        decision="auto_approved", status="paying",
        source_message_id=message.message_id,
    )
    try:
        result = adapter.pay(
            invoice_url=invoice_url, amount=amount, currency=currency,
            vendor_name=vendor_name, vendor_email=vendor_email,
            invoice_number=invoice_number,
        )
    except Exception as e:
        print(f"  ! payment failed: {e}")
        payments_store.update_status(payment_row["id"], "failed", decision="auto_approved")
        try:
            agentmail.inboxes.messages.reply(
                inbox.inbox_id, message.message_id,
                text=f"Payment failed: {e}\n\nRouting to {USER_EMAIL} for manual handling.",
            )
        except Exception:
            pass
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["payment-failed"])
        return

    # 5. Receipt to vendor + CC finance
    payments_store.update_status(payment_row["id"], "paid", transaction_id=result.get("transaction_id", ""))
    receipt = (
        f"Hi {vendor_name},\n\n"
        f"Confirming payment of {amount:.2f} {currency} for invoice "
        f"{invoice_number or '(no invoice number)'}.\n\n"
        f"Transaction id: {result.get('transaction_id', '(pending)')}\n"
        f"Network:        {result.get('network', PAYMENT_ADAPTER_NAME)}\n"
        f"Settled at:     {result.get('settled_at', datetime.utcnow().isoformat(timespec='seconds'))}\n\n"
        f"Thank you,\n{COMPANY_NAME}"
    )
    try:
        kwargs = {"text": receipt}
        if FINANCE_EMAIL:
            kwargs["cc"] = [FINANCE_EMAIL]
        agentmail.inboxes.messages.reply(inbox.inbox_id, message.message_id, **kwargs)
    except Exception as e:
        print(f"  ! receipt failed: {e}")

    print(f"  ✓ paid · tx={result.get('transaction_id', '')[:14]}...")
    _mark_read(inbox.inbox_id, message.message_id, add_labels=["paid"])


def _route_to_review(message, args, inbox, sender, reason: str,
                    row_amount: float | None = None, row_currency: str | None = None,
                    row_invoice: str | None = None):
    partial = args.get("partial_fields", {}) or {}
    vendor_name = args.get("vendor_name") or partial.get("vendor_name") or sender
    vendor_email = (args.get("vendor_email") or partial.get("vendor_email") or sender).lower()
    amount = row_amount if row_amount is not None else float(partial.get("amount") or args.get("amount") or 0)
    currency = row_currency or partial.get("currency") or args.get("currency") or PAYMENT_CURRENCY
    invoice_number = row_invoice or partial.get("invoice_number") or args.get("invoice_number") or ""
    summary = args.get("summary", "")

    row = payments_store.append(
        vendor_name=vendor_name, vendor_email=vendor_email, amount=amount,
        currency=currency, invoice_number=invoice_number,
        decision="needs_review", status="pending_review",
        source_message_id=message.message_id,
    )

    review_body = (
        f"[needs review · {reason}]\n\n"
        f"Summary: {summary}\n\n"
        f"  Vendor:  {vendor_name} ({vendor_email})\n"
        f"  Amount:  {amount:.2f} {currency}\n"
        f"  Invoice: {invoice_number or '(none)'}\n"
        f"  Reason:  {reason}\n\n"
        f"Reply to this thread with one word:\n"
        f"  approve  → fire payment via {PAYMENT_ADAPTER_NAME} adapter\n"
        f"  decline  → skip; vendor gets nothing\n"
        f"  decline: <reason>  → skip with reason logged\n\n"
        f"Payment id: {row['id']}\n\n— {COMPANY_NAME} Pay Agent"
    )
    try:
        agentmail.inboxes.messages.reply(
            inbox.inbox_id, message.message_id,
            to=[USER_EMAIL],
            text=review_body,
        )
        print(f"  ✓ review email sent to {USER_EMAIL}")
    except Exception as e:
        print(f"  ! review send failed: {e}")
    _mark_read(inbox.inbox_id, message.message_id, add_labels=["needs-review"])


def _handle_review_reply(message, pending, body, inbox, vendors):
    decision = reply_parser.parse(body)
    kind = decision["decision"]

    if kind == "unknown":
        try:
            agentmail.inboxes.messages.reply(
                inbox.inbox_id, message.message_id,
                text=(
                    "I couldn't parse your reply. Please reply with:\n"
                    "  approve  → pay\n"
                    "  decline  → skip\n"
                    "  decline: <reason>  → skip with reason\n\n"
                    f"— {COMPANY_NAME} Pay Agent"
                ),
            )
        except Exception:
            pass
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["unparseable"])
        return

    decided_text = body.strip().splitlines()[0][:200] if body.strip() else ""

    if kind == "decline":
        reason = decision.get("reason", "")
        payments_store.update_status(pending["id"], "skipped", decision=f"declined: {reason}" if reason else "declined")
        try:
            agentmail.inboxes.messages.reply(
                inbox.inbox_id, message.message_id,
                text=f"Skipped payment. Vendor was NOT contacted.\n\nDecision: {decided_text}\n\nPayment id: {pending['id']}\n\n— {COMPANY_NAME} Pay Agent",
            )
        except Exception:
            pass
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["declined"])
        return

    # Approve → fire the adapter using the saved row
    amount = float(pending["amount"])
    currency = pending["currency"]
    vendor_name = pending["vendor_name"]
    vendor_email = pending["vendor_email"]
    invoice_number = pending["invoice_number"]
    print(f"  → user approved ${amount:.2f} {currency} to {vendor_name} — paying")
    try:
        result = adapter.pay(
            invoice_url="",  # may be missing; the mock adapter handles empty url
            amount=amount, currency=currency,
            vendor_name=vendor_name, vendor_email=vendor_email,
            invoice_number=invoice_number,
        )
    except Exception as e:
        payments_store.update_status(pending["id"], "failed", decision="user_approved")
        try:
            agentmail.inboxes.messages.reply(
                inbox.inbox_id, message.message_id,
                text=f"Payment failed even after approval: {e}\n\nPayment id: {pending['id']}",
            )
        except Exception:
            pass
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["payment-failed"])
        return

    payments_store.update_status(
        pending["id"], "paid",
        transaction_id=result.get("transaction_id", ""),
        decision="user_approved",
    )

    # Send receipt to original vendor (on the original thread)
    receipt = (
        f"Hi {vendor_name},\n\n"
        f"Confirming payment of {amount:.2f} {currency} for invoice "
        f"{invoice_number or '(no invoice number)'}.\n\n"
        f"Transaction id: {result.get('transaction_id', '(pending)')}\n"
        f"Network:        {result.get('network', PAYMENT_ADAPTER_NAME)}\n\n"
        f"Thank you,\n{COMPANY_NAME}"
    )
    try:
        kwargs = {"text": receipt}
        if FINANCE_EMAIL:
            kwargs["cc"] = [FINANCE_EMAIL]
        agentmail.inboxes.messages.reply(
            inbox.inbox_id, pending["source_message_id"], **kwargs,
        )
    except Exception as e:
        print(f"  ! receipt to vendor failed: {e}")

    # Ack to user
    try:
        agentmail.inboxes.messages.reply(
            inbox.inbox_id, message.message_id,
            text=(
                f"Paid {amount:.2f} {currency} to {vendor_name}.\n\n"
                f"Transaction id: {result.get('transaction_id', '')}\n"
                f"Receipt sent to vendor (cc {FINANCE_EMAIL or 'none'}).\n\n"
                f"Payment id: {pending['id']}\n\n— {COMPANY_NAME} Pay Agent"
            ),
        )
    except Exception:
        pass

    _mark_read(inbox.inbox_id, message.message_id, add_labels=["paid-after-review"])


# --- main loop ----------------------------------------------------------------


def main():
    print(f"--- x402 Payment Agent  ·  {COMPANY_NAME} ---")
    inbox = get_or_create_inbox()
    vendors = vendors_store.load()
    print(f"Inbox:    {inbox.email}")
    print(f"Adapter:  {PAYMENT_ADAPTER_NAME}  ({adapter.__name__})")
    print(f"Vendors:  {len(vendors)} on allowlist")
    print(f"Caps:     per-vendor (vendors.csv) capped further by GLOBAL_MAX_USD={GLOBAL_MAX_USD}")
    print(f"Polling every {POLL_INTERVAL}s.\n")

    while True:
        try:
            vendors = vendors_store.load()
            unread = agentmail.inboxes.messages.list(inbox.inbox_id, labels=["unread"])
            messages = unread.messages or []
            if messages:
                print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {len(messages)} unread")
                for m in messages:
                    try:
                        process_message(m, inbox, vendors)
                    except Exception as e:
                        print(f"  ! error on {m.message_id}: {e}")
        except Exception as e:
            print(f"! poll loop error: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
