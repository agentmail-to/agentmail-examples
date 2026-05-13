"""
vendors.csv — allowlist of vendors approved for autonomous payment.

Schema:
  vendor_name, vendor_email, max_amount_usd, notes

A vendor is "trusted" if their email (case-insensitive) appears in this CSV.
Their per-vendor `max_amount_usd` overrides the global cap (lower of the two
applies). Re-read on every iteration so live edits to the file take effect.
"""

import csv
from pathlib import Path

FILE = Path("vendors.csv")


def load() -> list[dict]:
    if not FILE.exists():
        return []
    with FILE.open("r", newline="") as f:
        return [
            {
                "vendor_name": (r.get("vendor_name") or "").strip(),
                "vendor_email": (r.get("vendor_email") or "").strip().lower(),
                "max_amount_usd": float(r.get("max_amount_usd") or 0),
                "notes": (r.get("notes") or "").strip(),
            }
            for r in csv.DictReader(f)
        ]


def find(vendors: list[dict], sender_email: str) -> dict | None:
    """Look up a vendor by their email."""
    if not sender_email:
        return None
    target = sender_email.lower().strip()
    for v in vendors:
        if v["vendor_email"] == target:
            return v
    return None
