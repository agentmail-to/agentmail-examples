import os
import csv
import time
import json
from datetime import datetime, timezone

from agentmail import AgentMail
from openai import OpenAI

agentmail = AgentMail(api_key=os.environ["AGENTMAIL_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

RESEARCH_PROMPT = """Research the company at domain {domain}. Based on what you know, write 2-3 bullet points about:
- What the company does
- A recent development or noteworthy fact
- A potential pain point related to {our_product}

Return JSON: {{"bullets": ["...", "..."], "angle": "one sentence pitch angle"}}"""

EMAIL_PROMPT = """Write a cold email to {name} at {company}.

Research context:
{research}

Rules:
- Under 120 words
- Reference something specific about their company
- Clear ask: 15-minute call
- No fluff, no "I hope this finds you well"
- Sign off as {sender_name}

Return JSON: {{"subject": "...", "body": "..."}}"""

CLASSIFY_PROMPT = """Classify this reply to a cold sales email.
Return JSON: {{"category": "interested"|"not_interested"|"question"|"objection"|"out_of_office"}}

Reply: {text}"""

CALENDAR_LINK = os.environ.get("CALENDAR_LINK", "https://cal.com/your-link")
SENDER_NAME = os.environ.get("SENDER_NAME", "Your Name")
OUR_PRODUCT = os.environ.get("OUR_PRODUCT", "our product")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))


def llm_json(prompt: str) -> dict:
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def research_prospect(domain: str) -> dict:
    return llm_json(RESEARCH_PROMPT.format(domain=domain, our_product=OUR_PRODUCT))


def generate_email(name: str, company: str, research: dict) -> dict:
    research_text = "\n".join(research.get("bullets", [])) + "\nAngle: " + research.get("angle", "")
    return llm_json(EMAIL_PROMPT.format(
        name=name, company=company, research=research_text, sender_name=SENDER_NAME
    ))


def load_prospects(path: str = "prospects.csv") -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


def send_campaign(inbox_id: str, prospects: list[dict]) -> dict:
    tracker = {}
    for p in prospects:
        print(f"Researching {p['company']} ({p['domain']})...")
        research = research_prospect(p["domain"])

        email = generate_email(p["name"], p["company"], research)
        msg = agentmail.messages.send(
            inbox_id=inbox_id,
            to=[p["email"]],
            subject=email["subject"],
            text=email["body"],
            labels=["cold-outreach", "pending"],
        )
        tracker[p["email"]] = {
            "message_id": msg.id,
            "name": p["name"],
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        print(f"Sent to {p['name']} ({p['email']}): {email['subject']}")
    return tracker


def handle_replies(inbox_id: str, tracker: dict):
    messages = agentmail.messages.list(inbox_id=inbox_id, labels=["unread"])
    for msg in messages.data:
        sender = msg.from_address
        if sender not in tracker:
            continue

        result = llm_json(CLASSIFY_PROMPT.format(text=msg.text or ""))
        category = result.get("category", "question")

        agentmail.messages.update(
            inbox_id=inbox_id,
            message_id=msg.id,
            add_labels=[category],
            remove_labels=["unread", "pending"],
        )
        print(f"Reply from {sender}: {category}")

        if category == "interested":
            agentmail.messages.reply(
                inbox_id=inbox_id,
                message_id=msg.id,
                text=f"Great to hear! Here's my calendar link to book a time: {CALENDAR_LINK}\n\nLooking forward to it.\n{SENDER_NAME}",
            )
            print(f"Sent calendar link to {sender}")


def main():
    inbox = agentmail.inboxes.create(display_name="Sales Outreach")
    print(f"Created inbox: {inbox.email}")

    prospects = load_prospects()
    tracker = send_campaign(inbox.id, prospects)

    print(f"\nCampaign sent to {len(tracker)} prospects. Monitoring replies...")

    while True:
        handle_replies(inbox.id, tracker)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
