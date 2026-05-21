import os
import json
import time
from datetime import datetime, timezone

from agentmail import AgentMail
from openai import OpenAI

agentmail = AgentMail(api_key=os.environ["AGENTMAIL_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

REPORT_RECIPIENT = os.environ["REPORT_RECIPIENT"]
REPORT_DAY = os.environ.get("REPORT_DAY", "friday").lower()
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))

DAY_MAP = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}

PARSE_PROMPT = """Extract receipt details from this email.

From: {sender}
Subject: {subject}
Body:
{body}

Return JSON:
{{
  "vendor": "store or service name",
  "date": "YYYY-MM-DD",
  "items": [{{"description": "item name", "amount": 0.00}}],
  "subtotal": 0.00,
  "tax": 0.00,
  "total": 0.00,
  "currency": "USD",
  "category": "travel"|"meals"|"software"|"supplies"|"other"
}}

If this is not a receipt, return {{"error": "not a receipt"}}."""

expenses: list[dict] = []


def parse_receipt(sender: str, subject: str, body: str) -> dict:
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": PARSE_PROMPT.format(
            sender=sender, subject=subject, body=body
        )}],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def process_receipts(inbox_id: str):
    messages = agentmail.messages.list(inbox_id=inbox_id, labels=["unread"])
    for msg in messages.data:
        sender = msg.from_address or ""
        subject = msg.subject or ""
        body = msg.text or msg.html or ""

        agentmail.messages.update(
            inbox_id=inbox_id,
            message_id=msg.id,
            remove_labels=["unread"],
        )

        receipt = parse_receipt(sender, subject, body)
        if "error" in receipt:
            agentmail.messages.reply(
                inbox_id=inbox_id,
                message_id=msg.id,
                text="I could not parse a receipt from this email. Please forward the original receipt email.",
            )
            continue

        expenses.append(receipt)
        category = receipt.get("category", "other")

        agentmail.messages.update(
            inbox_id=inbox_id,
            message_id=msg.id,
            add_labels=["parsed", category],
        )

        agentmail.messages.reply(
            inbox_id=inbox_id,
            message_id=msg.id,
            text=(
                f"Receipt parsed:\n"
                f"Vendor: {receipt['vendor']}\n"
                f"Date: {receipt['date']}\n"
                f"Total: ${receipt['total']}\n"
                f"Category: {category}\n\n"
                f"Running total this period: ${sum(e['total'] for e in expenses):.2f} ({len(expenses)} receipts)"
            ),
        )
        print(f"Parsed: {receipt['vendor']} ${receipt['total']} ({category})")


def send_report(inbox_id: str):
    if not expenses:
        return

    by_category: dict[str, list[dict]] = {}
    for e in expenses:
        cat = e.get("category", "other")
        by_category.setdefault(cat, []).append(e)

    lines = [f"Expense Report - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}", "=" * 40, ""]
    grand_total = 0.0

    for cat, items in sorted(by_category.items()):
        cat_total = sum(i["total"] for i in items)
        grand_total += cat_total
        lines.append(f"## {cat.title()} (${cat_total:.2f})")
        for item in items:
            lines.append(f"  - {item['date']} | {item['vendor']} | ${item['total']:.2f}")
        lines.append("")

    lines.append(f"TOTAL: ${grand_total:.2f}")
    lines.append(f"Receipts: {len(expenses)}")

    agentmail.messages.send(
        inbox_id=inbox_id,
        to=[REPORT_RECIPIENT],
        subject=f"Weekly Expense Report - ${grand_total:.2f}",
        text="\n".join(lines),
        labels=["report"],
    )
    print(f"Sent expense report: ${grand_total:.2f} ({len(expenses)} receipts)")
    expenses.clear()


def should_send_report() -> bool:
    now = datetime.now(timezone.utc)
    return now.weekday() == DAY_MAP.get(REPORT_DAY, 4) and now.hour == 17 and now.minute < (POLL_INTERVAL // 60 + 1)


def main():
    inbox = agentmail.inboxes.create(display_name="Expense Tracker")
    print(f"Expense inbox: {inbox.email}")
    print(f"Forward receipts to this address.")
    print(f"Reports sent every {REPORT_DAY} to {REPORT_RECIPIENT}\n")

    while True:
        process_receipts(inbox.id)
        if should_send_report():
            send_report(inbox.id)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
