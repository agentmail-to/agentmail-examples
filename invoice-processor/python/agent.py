"""
AgentMail Invoice Processor — extract, match, route invoices.

Workflow per incoming email:
  1. Fetch the message + any PDF/image attachments.
  2. Pass the body + each attachment (as a Claude vision `document` block) to
     Claude with two tools:
       - extract_invoice(vendor, invoice_number, amount, currency, due_date, po_number, line_items)
       - cannot_extract(reason)
  3. If extracted:
       - Check duplicate (same invoice_number from same vendor) → skip + log
       - Match against open POs (purchase_orders.csv) by PO number, then by
         vendor + amount
       - Compute urgency (due_date within URGENT_DAYS)
       - Decide route:
           - matched + amount <= AUTO_APPROVE_LIMIT  →  auto_approved
           - matched + amount >  AUTO_APPROVE_LIMIT  →  needs_review (escalate)
           - no PO match                              →  needs_review (escalate)
       - Reply to vendor with status acknowledgment
       - Forward to AP_EMAIL if escalating
       - Append to invoice_log.csv

Run:
    pip install -r requirements.txt
    cp .env.example .env
    cp purchase_orders.example.csv purchase_orders.csv  # add your real POs
    python agent.py
"""

import base64
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path

from agentmail import AgentMail
from agentmail.inboxes import CreateInboxRequest
from anthropic import Anthropic
from dotenv import load_dotenv

import invoices
import purchase_orders
from prompt import build_system_prompt

load_dotenv()

# --- config -------------------------------------------------------------------

AGENTMAIL_API_KEY = os.environ["AGENTMAIL_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
COMPANY_NAME = os.getenv("COMPANY_NAME", "Accounts Payable")
AP_EMAIL = os.environ["AP_EMAIL"]
AUTO_APPROVE_LIMIT = float(os.getenv("AUTO_APPROVE_LIMIT", "5000"))
URGENT_DAYS = int(os.getenv("URGENT_DAYS", "3"))
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
INBOX_USERNAME = os.getenv("INBOX_USERNAME") or None

STATE_FILE = Path(".agent_state.json")

SUPPORTED_DOC_TYPES = {
    "application/pdf",
    "image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp",
}

# --- clients ------------------------------------------------------------------

agentmail = AgentMail(api_key=AGENTMAIL_API_KEY)
claude = Anthropic(api_key=ANTHROPIC_API_KEY)


# --- Claude tools -------------------------------------------------------------

EXTRACT_INVOICE_TOOL = {
    "name": "extract_invoice",
    "description": "Extract structured fields from an invoice document. Use ONLY when you can confidently identify the required fields verbatim.",
    "input_schema": {
        "type": "object",
        "required": ["vendor_name", "invoice_number", "amount", "currency", "due_date"],
        "properties": {
            "vendor_name": {"type": "string", "description": "Company name on the 'Bill From' / letterhead. Not your own company."},
            "invoice_number": {"type": "string", "description": "The invoice ID printed on the document. Verbatim."},
            "amount": {"type": "number", "description": "Grand total amount due (after taxes, fees, discounts)."},
            "currency": {"type": "string", "description": "ISO 4217 code (USD, EUR, GBP, ...)."},
            "due_date": {"type": "string", "description": "Absolute ISO date 'YYYY-MM-DD'. Empty string if not stated."},
            "po_number": {"type": "string", "description": "Purchase order number if cited. Empty string if not."},
            "line_items": {"type": "string", "description": "Brief one-line summary of what was billed (optional)."},
            "notes": {"type": "string", "description": "Anything else relevant — early-pay discounts, credit memos, partial billings."},
        },
    },
}

CANNOT_EXTRACT_TOOL = {
    "name": "cannot_extract",
    "description": "Email is not an invoice OR critical fields are missing/unreadable.",
    "input_schema": {
        "type": "object",
        "required": ["reason"],
        "properties": {"reason": {"type": "string"}},
    },
}

TOOLS = [EXTRACT_INVOICE_TOOL, CANNOT_EXTRACT_TOOL]


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
            display_name=f"{COMPANY_NAME} - Accounts Payable",
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


def _fetch_attachment_bytes(inbox_id: str, message_id: str, attachment_id: str) -> tuple[bytes, str] | None:
    """Returns (bytes, content_type) or None on failure."""
    try:
        meta = agentmail.inboxes.messages.get_attachment(inbox_id, message_id, attachment_id)
        ct = (meta.content_type or "").lower()
        if ct not in SUPPORTED_DOC_TYPES:
            return None
        # download_url is a presigned URL valid until meta.expires_at
        with urllib.request.urlopen(meta.download_url, timeout=30) as r:
            data = r.read()
        return data, ct
    except Exception as e:
        print(f"  ! attachment fetch failed: {e}")
        return None


def _build_content_blocks(text_body: str, attachments: list[tuple[bytes, str, str]]) -> list:
    """Build the content blocks for Claude — text + each attachment as a vision document.
    attachments is a list of (bytes, content_type, filename)."""
    blocks: list = []
    if text_body.strip():
        blocks.append({"type": "text", "text": f"Email body:\n{text_body[:4000]}"})
    for data, ct, filename in attachments:
        b64 = base64.standard_b64encode(data).decode("ascii")
        if ct == "application/pdf":
            blocks.append({
                "type": "document",
                "source": {"type": "base64", "media_type": ct, "data": b64},
                "title": filename or "invoice.pdf",
            })
        else:  # image
            blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": ct, "data": b64},
            })
    if not blocks:
        blocks.append({"type": "text", "text": "(empty email — no body, no attachments)"})
    return blocks


# --- routing ------------------------------------------------------------------


def _is_urgent(due_date_str: str) -> tuple[bool, int | None]:
    """Returns (is_urgent, days_until_due). Empty due_date → (False, None)."""
    if not due_date_str:
        return False, None
    try:
        due = datetime.fromisoformat(due_date_str).date()
    except Exception:
        return False, None
    today = datetime.now(timezone.utc).date()
    days = (due - today).days
    return days <= URGENT_DAYS, days


def _vendor_ack_body(invoice: dict, status: str, urgent_days: int | None,
                     po_match: dict | None) -> str:
    """Templated acknowledgment to the vendor based on routing decision."""
    vendor = invoice.get("vendor_name", "")
    inv_num = invoice.get("invoice_number", "")
    amount = invoice.get("amount", 0)
    currency = invoice.get("currency", "USD")

    lines = [
        f"Hi {vendor},",
        "",
        "Thanks for the invoice. Recording the following:",
        "",
        f"  Invoice: {inv_num}",
        f"  Amount: {amount:,.2f} {currency}",
    ]
    if invoice.get("due_date"):
        lines.append(f"  Due:    {invoice['due_date']}")
    if invoice.get("po_number"):
        lines.append(f"  PO:     {invoice['po_number']}")
    lines.append("")

    if status == "auto_approved":
        lines.append(
            f"This invoice has been auto-approved (under our auto-approve "
            f"limit) and is in the payment queue. You'll receive payment per "
            f"PO {po_match['po_number']} terms."
        )
    elif status == "needs_review_no_po":
        lines.append(
            f"We don't see a matching open purchase order for this invoice. "
            f"To process payment, please reply with the PO reference. We've "
            f"flagged this for our AP team in the meantime."
        )
    elif status == "needs_review_over_limit":
        lines.append(
            f"This invoice exceeds our auto-approve threshold and has been "
            f"forwarded to our AP team for review. Expect confirmation within "
            f"2 business days."
        )
    elif status == "duplicate":
        lines.append(
            f"This invoice number was already received and processed. If you "
            f"believe this is in error, reply with details."
        )
    else:
        lines.append("This invoice is being routed for processing.")

    if urgent_days is not None and urgent_days <= URGENT_DAYS:
        lines.insert(-1, f"⚠️  Marked URGENT (due in {urgent_days} day(s)).")
        lines.insert(-1, "")

    lines.append("")
    lines.append(f"— {COMPANY_NAME} Accounts Payable")
    return "\n".join(lines)


def _ap_handoff_body(invoice: dict, status: str, urgent_days: int | None,
                     po_match: dict | None) -> str:
    """Cover note for the forward to AP_EMAIL on escalations."""
    reason = {
        "needs_review_no_po": "NO MATCHING PO FOUND — vendor needs to send PO reference.",
        "needs_review_over_limit": f"OVER AUTO-APPROVE LIMIT (${AUTO_APPROVE_LIMIT:,.0f}).",
    }.get(status, "ESCALATED")
    urgent_line = f"⚠️  URGENT — due in {urgent_days} day(s)\n\n" if urgent_days is not None and urgent_days <= URGENT_DAYS else ""
    po_line = f"\nMatched PO: {po_match['po_number']} ({po_match['description']})" if po_match else "\nMatched PO: none"
    return (
        f"[INVOICE FLAGGED FOR REVIEW]\n\n"
        f"{urgent_line}"
        f"Reason: {reason}\n\n"
        f"Vendor: {invoice.get('vendor_name', '')}\n"
        f"Invoice #: {invoice.get('invoice_number', '')}\n"
        f"Amount: {invoice.get('amount', 0):,.2f} {invoice.get('currency', 'USD')}\n"
        f"Due: {invoice.get('due_date', '(not stated)')}\n"
        f"PO cited on invoice: {invoice.get('po_number', '(none)')}{po_line}\n\n"
        f"Notes: {invoice.get('notes', '(none)')}\n"
        f"Line items: {invoice.get('line_items', '(none)')}\n\n"
        f"---\n"
        f"Original email + invoice attachment forwarded below."
    )


# --- core processing ----------------------------------------------------------


def process_message(message, inbox):
    print(f"  → fetching message + attachments")
    full = agentmail.inboxes.messages.get(inbox.inbox_id, message.message_id)

    # Pull text body. AgentMail's `extracted_text` strips quoted replies, but
    # for invoice emails it sometimes drops the body content too (especially
    # when the invoice uses indented / code-block formatting). Use whichever
    # is longer — losing extra quoted history is fine; losing the invoice
    # body is fatal.
    extracted = (getattr(full, "extracted_text", None) or "").strip()
    raw = (full.text or "").strip()
    text_body = raw if len(raw) > len(extracted) * 1.5 else (extracted or raw)

    # Fetch attachments — only PDFs/images
    attachments_for_claude: list[tuple[bytes, str, str]] = []
    raw_attachments = getattr(full, "attachments", None) or []
    for att in raw_attachments:
        result = _fetch_attachment_bytes(inbox.inbox_id, full.message_id, att.attachment_id)
        if result:
            data, ct = result
            attachments_for_claude.append((data, ct, getattr(att, "filename", "")))

    if not text_body and not attachments_for_claude:
        print("  ! empty email and no usable attachments, skipping")
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["empty"])
        return

    print(f"  → asking Claude to extract (model={MODEL}, {len(attachments_for_claude)} attachment(s))")
    response = claude.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=build_system_prompt(inbox_email=inbox.email),
        tools=TOOLS,
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": _build_content_blocks(text_body, attachments_for_claude)}],
    )

    invoice = None
    cannot_extract_reason = None
    for block in response.content:
        if block.type == "tool_use":
            if block.name == "extract_invoice":
                invoice = block.input
            elif block.name == "cannot_extract":
                cannot_extract_reason = block.input.get("reason", "")

    if cannot_extract_reason or not invoice:
        reason = cannot_extract_reason or "no tool called"
        print(f"  ⏭  cannot extract: {reason}")
        invoices.log_action(
            action="rejected", note=reason, thread_id=message.thread_id,
        )
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["non_invoice"])
        return

    inv_num = (invoice.get("invoice_number") or "").strip()
    if not inv_num:
        print("  ! no invoice number, refusing to process")
        invoices.log_action(action="rejected", note="no invoice number",
                           thread_id=message.thread_id)
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["no_invoice_number"])
        return

    # Duplicate check
    if invoices.is_duplicate(inv_num, invoice.get("vendor_name", "")):
        print(f"  ⏭  duplicate: {inv_num}")
        body = _vendor_ack_body(invoice, "duplicate", None, None)
        agentmail.inboxes.messages.reply(
            inbox.inbox_id, message.message_id, text=body
        )
        invoices.log_action(
            action="duplicate", vendor=invoice.get("vendor_name", ""),
            invoice_number=inv_num, status="duplicate",
            thread_id=message.thread_id,
        )
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["duplicate"])
        return

    # PO match
    po_match = purchase_orders.find_match(
        po_number=invoice.get("po_number"),
        vendor_name=invoice.get("vendor_name"),
        amount=invoice.get("amount"),
    )

    # Urgency
    is_urgent, urgent_days = _is_urgent(invoice.get("due_date", ""))

    # Routing decision
    amount = float(invoice.get("amount") or 0)
    if not po_match:
        status = "needs_review_no_po"
    elif amount > AUTO_APPROVE_LIMIT:
        status = "needs_review_over_limit"
    else:
        status = "auto_approved"

    print(
        f"  📄 extracted: {invoice.get('vendor_name')} #{inv_num} "
        f"{amount:,.2f} {invoice.get('currency', 'USD')} → {status}"
        f"{' (URGENT)' if is_urgent else ''}"
    )

    # Vendor acknowledgment
    ack = _vendor_ack_body(invoice, status, urgent_days, po_match)
    agentmail.inboxes.messages.reply(
        inbox.inbox_id, message.message_id, text=ack
    )

    # Forward to AP team if escalating
    if status.startswith("needs_review"):
        try:
            handoff = _ap_handoff_body(invoice, status, urgent_days, po_match)
            agentmail.inboxes.messages.forward(
                inbox.inbox_id, message.message_id,
                to=[AP_EMAIL],
                text=handoff,
            )
            print(f"  ⚠️  escalation forwarded to {AP_EMAIL}")
        except Exception as e:
            print(f"  ! escalation forward failed: {e}")

    # Record + log
    invoices.record_processed({
        "vendor": invoice.get("vendor_name", ""),
        "invoice_number": inv_num,
        "amount": amount,
        "currency": invoice.get("currency", "USD"),
        "due_date": invoice.get("due_date", ""),
        "po_number": invoice.get("po_number", ""),
        "po_match": po_match["po_number"] if po_match else None,
        "status": status,
        "is_urgent": is_urgent,
        "message_id": full.message_id,
        "thread_id": full.thread_id,
    })
    invoices.log_action(
        action="processed",
        vendor=invoice.get("vendor_name", ""),
        invoice_number=inv_num,
        amount=str(amount),
        currency=invoice.get("currency", "USD"),
        due_date=invoice.get("due_date", ""),
        po_number=invoice.get("po_number", ""),
        status=status,
        thread_id=message.thread_id,
        note=f"urgent={is_urgent}, po_match={po_match['po_number'] if po_match else 'none'}",
    )

    label_status = "urgent_" + status if is_urgent else status
    _mark_read(inbox.inbox_id, message.message_id, add_labels=[label_status])


# --- main loop ----------------------------------------------------------------


def main():
    inbox = get_or_create_inbox()
    print(f"\n📬 Invoice processor live at: {inbox.email}")
    print(f"   Forward vendor invoices to that address.")
    print(f"   Auto-approve limit: {AUTO_APPROVE_LIMIT:,.0f} (above → escalate to {AP_EMAIL})")
    print(f"   Urgent threshold: {URGENT_DAYS} day(s) before due_date")
    print(f"   Open POs loaded: {len(purchase_orders.load_all())}")
    print(f"   Polling every {POLL_INTERVAL}s. Ctrl-C to stop.\n")

    seen: set[str] = set()
    while True:
        try:
            resp = agentmail.inboxes.messages.list(
                inbox.inbox_id, labels=["unread"]
            )
            new_msgs = [m for m in (resp.messages or []) if m.message_id not in seen]
            for m in new_msgs:
                seen.add(m.message_id)
                if _sender_email(m) == inbox.email.lower():
                    continue
                print(f"\n📩 from {_sender_email(m)}: {(m.subject or '(no subject)')[:60]}")
                try:
                    process_message(m, inbox)
                except Exception as e:
                    print(f"  ! error processing message: {e}")
        except Exception as e:
            print(f"poll error: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
