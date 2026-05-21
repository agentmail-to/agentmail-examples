"""
payments.csv — append-only audit ledger of every payment attempt.

Schema:
  id, vendor_name, vendor_email, amount, currency, status,
  transaction_id, invoice_number, decision, decided_at, source_message_id, created
"""

import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path

FILE = Path("payments.csv")
HEADER = [
    "id", "vendor_name", "vendor_email", "amount", "currency", "status",
    "transaction_id", "invoice_number", "decision", "decided_at",
    "source_message_id", "created",
]


def _ensure_header() -> None:
    if not FILE.exists():
        with FILE.open("w", newline="") as f:
            csv.writer(f).writerow(HEADER)


def _payment_id(invoice_number: str, vendor_email: str, amount: float) -> str:
    return hashlib.sha1(
        f"{invoice_number}|{vendor_email}|{amount:.2f}".encode()
    ).hexdigest()[:12]


def _read_all() -> list[dict]:
    if not FILE.exists():
        return []
    with FILE.open("r", newline="") as f:
        return list(csv.DictReader(f))


def _write_all(rows: list[dict]) -> None:
    _ensure_header()
    with FILE.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in HEADER})


def is_duplicate(invoice_number: str, vendor_email: str) -> bool:
    if not invoice_number:
        return False
    for r in _read_all():
        if r["invoice_number"] == invoice_number and r["vendor_email"].lower() == vendor_email.lower():
            return True
    return False


def append(*, vendor_name: str, vendor_email: str, amount: float, currency: str,
           invoice_number: str, decision: str, status: str,
           transaction_id: str = "", source_message_id: str = "") -> dict:
    """Append a row. status: 'paid' | 'pending_review' | 'failed' | 'skipped'."""
    _ensure_header()
    pid = _payment_id(invoice_number or source_message_id, vendor_email, amount)
    row = {
        "id": pid,
        "vendor_name": vendor_name,
        "vendor_email": vendor_email.lower(),
        "amount": f"{amount:.2f}",
        "currency": currency,
        "status": status,
        "transaction_id": transaction_id,
        "invoice_number": invoice_number,
        "decision": decision,
        "decided_at": datetime.now(timezone.utc).isoformat(timespec="seconds") if status in {"paid", "failed"} else "",
        "source_message_id": source_message_id,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with FILE.open("a", newline="") as f:
        csv.DictWriter(f, fieldnames=HEADER).writerow(row)
    return row


def update_status(payment_id: str, status: str, transaction_id: str = "", decision: str = "") -> bool:
    rows = _read_all()
    n = 0
    for r in rows:
        if r["id"] == payment_id:
            r["status"] = status
            if transaction_id:
                r["transaction_id"] = transaction_id
            if decision:
                r["decision"] = decision
            r["decided_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            n += 1
    if n:
        _write_all(rows)
    return n > 0


def find_pending_by_id(payment_id: str) -> dict | None:
    for r in _read_all():
        if r["id"] == payment_id and r["status"] == "pending_review":
            return r
    return None


def find_pending_by_thread(source_message_id: str) -> dict | None:
    for r in reversed(_read_all()):
        if r["source_message_id"] == source_message_id and r["status"] == "pending_review":
            return r
    return None
