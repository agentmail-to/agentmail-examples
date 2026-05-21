"""
Processed-invoice tracker (for duplicate detection) + audit log.

Two files:
  invoices.json  — { "processed": [{invoice_number, vendor, message_id, ...}] }
  invoice_log.csv — append-only ledger of every action.
"""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

PROCESSED_FILE = Path("invoices.json")
LOG_FILE = Path("invoice_log.csv")

LOG_COLUMNS = [
    "timestamp_utc", "action", "vendor", "invoice_number",
    "amount", "currency", "due_date", "po_number", "status",
    "thread_id", "note",
]


def _load() -> dict:
    if not PROCESSED_FILE.exists():
        return {"processed": []}
    try:
        return json.loads(PROCESSED_FILE.read_text())
    except Exception:
        return {"processed": []}


def _save(state: dict) -> None:
    PROCESSED_FILE.write_text(json.dumps(state, indent=2))


def is_duplicate(invoice_number: str, vendor: str = "") -> bool:
    """Same invoice_number from the same vendor counts as duplicate.
    Without vendor, any matching invoice_number does."""
    if not invoice_number:
        return False
    state = _load()
    inv_clean = invoice_number.strip()
    v_clean = (vendor or "").strip().lower()
    for p in state.get("processed", []):
        if p.get("invoice_number", "").strip() == inv_clean:
            if not v_clean or (p.get("vendor", "").strip().lower() == v_clean):
                return True
    return False


def record_processed(invoice: dict) -> None:
    state = _load()
    state["processed"].append({
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **invoice,
    })
    _save(state)


def _ensure_log_header() -> None:
    if not LOG_FILE.exists() or LOG_FILE.stat().st_size == 0:
        with LOG_FILE.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(LOG_COLUMNS)


def log_action(*, action: str, vendor: str = "", invoice_number: str = "",
               amount: str = "", currency: str = "", due_date: str = "",
               po_number: str = "", status: str = "", thread_id: str = "",
               note: str = "") -> None:
    _ensure_log_header()
    row = [
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
        action, vendor, invoice_number, amount, currency, due_date,
        po_number, status, thread_id,
        note.replace("\n", " ")[:500],
    ]
    with LOG_FILE.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)
