"""
CSV-backed open purchase order list.

`purchase_orders.csv` columns:
  po_number, vendor_name, amount, currency, description, status

The agent matches incoming invoices against this list to decide auto-approve
vs escalate. Match priority:
  1. Exact PO number (best signal — invoice cites the PO)
  2. Vendor name + amount within $1 (fallback for invoices missing PO ref)
"""

import csv
from pathlib import Path

PO_FILE = Path("purchase_orders.csv")


def load_all() -> list[dict]:
    if not PO_FILE.exists():
        return []
    with PO_FILE.open(newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f)]


def find_match(po_number: str | None, vendor_name: str | None,
               amount: float | None) -> dict | None:
    """Find an open PO matching the invoice."""
    rows = [r for r in load_all() if (r.get("status") or "open").lower() == "open"]

    # Strategy 1: exact PO number match
    if po_number:
        po_clean = po_number.strip().upper()
        for r in rows:
            if (r.get("po_number") or "").strip().upper() == po_clean:
                return r

    # Strategy 2: vendor name + amount within $1 tolerance
    if vendor_name and amount is not None:
        v_clean = vendor_name.strip().lower()
        for r in rows:
            v_match = (r.get("vendor_name") or "").strip().lower() == v_clean
            try:
                a_match = abs(float(r.get("amount") or 0) - float(amount)) <= 1.0
            except Exception:
                a_match = False
            if v_match and a_match:
                return r

    return None
