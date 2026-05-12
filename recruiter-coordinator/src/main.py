import os
import csv
import time
import json
from datetime import datetime, timedelta, timezone

from agentmail import AgentMail
from openai import OpenAI

from config import FOLLOW_UP_DELAY_HOURS, POLL_INTERVAL_SECONDS, MAX_FOLLOW_UPS

agentmail = AgentMail(api_key=os.environ["AGENTMAIL_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

CLASSIFY_PROMPT = """Classify this email reply from a recruiting candidate.
Return JSON with one field: "category" which is one of:
"interested", "not_interested", "question", "scheduling"

Email text:
{text}"""

OUTREACH_PROMPT = """Write a short, warm recruiting outreach email to {name} about the {role} role at {company}.
Keep it under 150 words. Be direct, not salesy. Do not include a subject line."""


def generate_outreach(name: str, role: str, company: str) -> dict:
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": OUTREACH_PROMPT.format(
            name=name, role=role, company=company
        )}],
    )
    body = resp.choices[0].message.content
    subject = f"{role} opportunity at {company}"
    return {"subject": subject, "body": body}


def classify_reply(text: str) -> str:
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": CLASSIFY_PROMPT.format(text=text)}],
        response_format={"type": "json_object"},
    )
    result = json.loads(resp.choices[0].message.content)
    return result.get("category", "question")


def load_candidates(path: str = "candidates.csv") -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


def send_outreach(inbox_id: str, candidates: list[dict]) -> dict:
    sent = {}
    for c in candidates:
        email_content = generate_outreach(c["name"], c["role"], c["company"])
        msg = agentmail.messages.send(
            inbox_id=inbox_id,
            to=[c["email"]],
            subject=email_content["subject"],
            text=email_content["body"],
            labels=["outreach"],
        )
        sent[c["email"]] = {
            "message_id": msg.id,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "follow_ups": 0,
            "name": c["name"],
            "role": c["role"],
            "company": c["company"],
        }
        print(f"Sent outreach to {c['name']} ({c['email']})")
    return sent


def process_replies(inbox_id: str, tracker: dict):
    messages = agentmail.messages.list(inbox_id=inbox_id, labels=["unread"])
    for msg in messages.data:
        sender = msg.from_address
        if sender not in tracker:
            continue

        category = classify_reply(msg.text or "")
        agentmail.messages.update(
            inbox_id=inbox_id,
            message_id=msg.id,
            add_labels=[category, "replied"],
            remove_labels=["unread"],
        )
        tracker[sender]["replied"] = True
        print(f"Classified reply from {sender} as: {category}")


def send_follow_ups(inbox_id: str, tracker: dict):
    now = datetime.now(timezone.utc)
    for email, data in tracker.items():
        if data.get("replied"):
            continue
        if data["follow_ups"] >= MAX_FOLLOW_UPS:
            continue
        sent_at = datetime.fromisoformat(data["sent_at"])
        if now - sent_at < timedelta(hours=FOLLOW_UP_DELAY_HOURS):
            continue

        agentmail.messages.send(
            inbox_id=inbox_id,
            to=[email],
            subject=f"Following up - {data['role']} at {data['company']}",
            text=f"Hi {data['name']}, just wanted to follow up on my previous email about the {data['role']} role. Would love to chat if you're interested.",
            labels=["follow-up"],
        )
        data["follow_ups"] += 1
        data["sent_at"] = now.isoformat()
        print(f"Sent follow-up #{data['follow_ups']} to {data['name']}")


def main():
    inbox = agentmail.inboxes.create(display_name="Recruiter Coordinator")
    inbox_id = inbox.id
    print(f"Created inbox: {inbox.email}")

    candidates = load_candidates()
    tracker = send_outreach(inbox_id, candidates)

    print(f"\nOutreach sent to {len(tracker)} candidates. Monitoring inbox...")

    while True:
        process_replies(inbox_id, tracker)
        send_follow_ups(inbox_id, tracker)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
