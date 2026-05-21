import os
import csv
import json
import time
from datetime import datetime, timedelta, timezone

from agentmail import AgentMail
from openai import OpenAI

agentmail = AgentMail(api_key=os.environ["AGENTMAIL_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "120"))
COMPANY_NAME = os.environ.get("COMPANY_NAME", "Your Company")
ESCALATION_EMAIL = os.environ.get("ESCALATION_EMAIL", "finance@yourcompany.com")

REMINDER_SCHEDULE = [
    {"days_overdue": 1, "tone": "friendly", "label": "reminder-1"},
    {"days_overdue": 7, "tone": "firm", "label": "reminder-2"},
    {"days_overdue": 14, "tone": "urgent", "label": "reminder-3"},
    {"days_overdue": 30, "tone": "final-notice", "label": "final-notice"},
]

REMINDER_PROMPT = """Write a {tone} payment reminder email.

Details:
- Customer: {name}
- Invoice: #{invoice_id}
- Amount: ${amount}
- Due date: {due_date}
- Days overdue: {days_overdue}

Keep it under 100 words. Professional. Sign as {company} Accounts Receivable."""

CLASSIFY_PROMPT = """Classify this reply to a payment collection email.
Return JSON: {{"category": "paid"|"dispute"|"payment_plan"|"question"|"other", "summary": "one sentence summary"}}

Reply: {text}"""


def llm_text(prompt: str) -> str:
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def llm_json(prompt: str) -> dict:
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def load_invoices(path: str = "invoices.csv") -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


def get_days_overdue(due_date_str: str) -> int:
    due = datetime.strptime(due_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - due).days


def send_reminders(inbox_id: str, tracker: dict):
    for email, data in tracker.items():
        if data.get("resolved"):
            continue

        days = get_days_overdue(data["due_date"])
        if days < 1:
            continue

        current_stage = data.get("current_stage", -1)
        for i, stage in enumerate(REMINDER_SCHEDULE):
            if i <= current_stage:
                continue
            if days < stage["days_overdue"]:
                break

            reminder = llm_text(REMINDER_PROMPT.format(
                tone=stage["tone"],
                name=data["name"],
                invoice_id=data["invoice_id"],
                amount=data["amount"],
                due_date=data["due_date"],
                days_overdue=days,
                company=COMPANY_NAME,
            ))
            agentmail.messages.send(
                inbox_id=inbox_id,
                to=[email],
                subject=f"Payment reminder: Invoice #{data['invoice_id']} - ${data['amount']}",
                text=reminder,
                labels=[stage["label"], "collections"],
            )
            data["current_stage"] = i
            print(f"Sent {stage['label']} to {data['name']} ({days} days overdue, ${data['amount']})")


def handle_replies(inbox_id: str, tracker: dict):
    messages = agentmail.messages.list(inbox_id=inbox_id, labels=["unread"])
    for msg in messages.data:
        sender = msg.from_address
        if sender not in tracker:
            continue

        result = llm_json(CLASSIFY_PROMPT.format(text=msg.text or ""))
        category = result.get("category", "other")

        agentmail.messages.update(
            inbox_id=inbox_id,
            message_id=msg.id,
            add_labels=[category],
            remove_labels=["unread"],
        )

        if category == "paid":
            tracker[sender]["resolved"] = True
            agentmail.messages.reply(
                inbox_id=inbox_id,
                message_id=msg.id,
                text=f"Thank you for your payment on Invoice #{tracker[sender]['invoice_id']}. We appreciate your prompt attention to this matter.\n\n{COMPANY_NAME} Accounts Receivable",
            )
            print(f"Marked {sender} as paid")
        elif category in ("dispute", "payment_plan"):
            agentmail.messages.send(
                inbox_id=inbox_id,
                to=[ESCALATION_EMAIL],
                subject=f"[Collections Escalation] {category}: Invoice #{tracker[sender]['invoice_id']}",
                text=f"Customer: {tracker[sender]['name']} ({sender})\nCategory: {category}\nSummary: {result.get('summary', '')}\n\nOriginal reply:\n{msg.text}",
                labels=["escalated"],
            )
            print(f"Escalated {category} from {sender} to {ESCALATION_EMAIL}")


def print_report(tracker: dict):
    total = len(tracker)
    resolved = sum(1 for d in tracker.values() if d.get("resolved"))
    print(f"\n--- Collections Report: {resolved}/{total} resolved ---")


def main():
    inbox = agentmail.inboxes.create(display_name=f"{COMPANY_NAME} Collections")
    print(f"Created collections inbox: {inbox.email}")

    invoices = load_invoices()
    tracker = {}
    for inv in invoices:
        tracker[inv["email"]] = {
            "name": inv["name"],
            "amount": inv["amount"],
            "due_date": inv["due_date"],
            "invoice_id": inv["invoice_id"],
            "current_stage": -1,
            "resolved": False,
        }

    print(f"Tracking {len(tracker)} invoices. Monitoring...\n")

    while True:
        send_reminders(inbox.id, tracker)
        handle_replies(inbox.id, tracker)
        print_report(tracker)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
