"""
signals.csv — append-only audit log of every classification.

Schema:
  timestamp, message_id, sender, classification, sentiment_or_event,
  amount_usd, customer, summary, slack_fired
"""

import csv
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path("signals.csv")
HEADER = [
    "timestamp", "message_id", "sender", "classification",
    "sentiment_or_event", "amount_usd", "customer", "summary", "slack_fired",
]


def _ensure_header() -> None:
    if not LOG_FILE.exists():
        with LOG_FILE.open("w", newline="") as f:
            csv.writer(f).writerow(HEADER)


def log(
    *,
    message_id: str,
    sender: str,
    classification: str,
    sentiment_or_event: str = "",
    amount_usd: float | int = 0,
    customer: str = "",
    summary: str = "",
    slack_fired: bool = False,
) -> None:
    _ensure_header()
    with LOG_FILE.open("a", newline="") as f:
        csv.writer(f).writerow([
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            message_id,
            sender,
            classification,
            sentiment_or_event,
            f"{float(amount_usd):.2f}" if amount_usd else "",
            customer,
            (summary or "").replace("\n", " ").strip()[:300],
            "yes" if slack_fired else "no",
        ])


def read_today() -> list[dict]:
    """Return all rows logged today (UTC) for the EOD digest."""
    if not LOG_FILE.exists():
        return []
    today_iso = datetime.now(timezone.utc).date().isoformat()
    rows: list[dict] = []
    with LOG_FILE.open("r", newline="") as f:
        for row in csv.DictReader(f):
            ts = row.get("timestamp") or ""
            if ts.startswith(today_iso):
                rows.append(row)
    return rows
