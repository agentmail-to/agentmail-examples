import os
import csv
import json
import time
from datetime import datetime, timezone

from agentmail import AgentMail
from openai import OpenAI

agentmail = AgentMail(api_key=os.environ["AGENTMAIL_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "120"))
GUEST_NAME = os.environ.get("GUEST_NAME", "Your Name")
GUEST_BIO = os.environ.get("GUEST_BIO", "Founder and builder")
CALENDAR_LINK = os.environ.get("CALENDAR_LINK", "https://cal.com/your-link")

PITCH_PROMPT = """Write a personalized podcast guest pitch email.

Guest: {guest_name}
Guest bio: {guest_bio}
Show: {show_name}
Host: {host_name}
Show topic/focus: {show_topic}

Rules:
- Under 150 words
- Reference the show's specific focus
- Propose 2-3 concrete episode topic ideas
- Direct, no fluff
- Sign as {guest_name}

Return JSON: {{"subject": "...", "body": "..."}}"""

CLASSIFY_PROMPT = """Classify this reply to a podcast booking pitch.
Return JSON: {{"category": "interested"|"declined"|"question"|"scheduling"|"other"}}

Reply: {text}"""


def llm_json(prompt: str) -> dict:
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def load_podcasts(path: str = "podcasts.csv") -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


def send_pitches(inbox_id: str, podcasts: list[dict]) -> dict:
    tracker = {}
    for p in podcasts:
        pitch = llm_json(PITCH_PROMPT.format(
            guest_name=GUEST_NAME,
            guest_bio=GUEST_BIO,
            show_name=p["show_name"],
            host_name=p["host_name"],
            show_topic=p["show_topic"],
        ))

        msg = agentmail.messages.send(
            inbox_id=inbox_id,
            to=[p["host_email"]],
            subject=pitch["subject"],
            text=pitch["body"],
            labels=["pitched"],
        )
        tracker[p["host_email"]] = {
            "show_name": p["show_name"],
            "host_name": p["host_name"],
            "message_id": msg.id,
            "stage": "pitched",
        }
        print(f"Pitched: {p['show_name']} ({p['host_name']})")
    return tracker


def handle_replies(inbox_id: str, tracker: dict):
    messages = agentmail.messages.list(inbox_id=inbox_id, labels=["unread"])
    for msg in messages.data:
        sender = msg.from_address or ""
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

        show = tracker[sender]["show_name"]
        tracker[sender]["stage"] = category
        print(f"Reply from {show}: {category}")

        if category in ("interested", "scheduling"):
            agentmail.messages.reply(
                inbox_id=inbox_id,
                message_id=msg.id,
                text=(
                    f"Great to hear, {tracker[sender]['host_name']}! "
                    f"Here is my calendar link to find a time that works: {CALENDAR_LINK}\n\n"
                    f"Looking forward to it.\n{GUEST_NAME}"
                ),
            )
            agentmail.messages.update(inbox_id=inbox_id, message_id=msg.id, add_labels=["booked"])
            print(f"  Sent calendar link for {show}")


def print_status(tracker: dict):
    print(f"\n--- Booking Status ({len(tracker)} shows) ---")
    for email, data in tracker.items():
        print(f"  {data['show_name']}: {data['stage']}")
    print()


def main():
    inbox = agentmail.inboxes.create(display_name=f"{GUEST_NAME} Podcast Booking")
    print(f"Booking inbox: {inbox.email}\n")

    podcasts = load_podcasts()
    tracker = send_pitches(inbox.id, podcasts)

    print(f"\nPitched {len(tracker)} shows. Monitoring replies...\n")

    while True:
        handle_replies(inbox.id, tracker)
        print_status(tracker)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
