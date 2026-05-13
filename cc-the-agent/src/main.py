import os
import re
import json
import time

from agentmail import AgentMail
from openai import OpenAI

agentmail = AgentMail(api_key=os.environ["AGENTMAIL_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

DEFAULT_MODE = os.environ.get("DEFAULT_MODE", "auto")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "15"))

ANALYSIS_PROMPT = """You are an email assistant. Analyze this email and provide a {mode} response.

Modes:
- summarize: 3-sentence summary of the key points
- action-items: bullet list of action items with owners and deadlines
- draft-reply: a suggested reply the user can edit and send
- auto: pick whichever response type is most useful for this email

From: {sender}
To: {to}
CC: {cc}
Subject: {subject}
Body:
{body}

Respond with the analysis only. No preamble."""


def detect_mode(subject: str) -> str:
    match = re.match(r"\[(\w[\w-]*)\]\s*", subject)
    if match:
        mode = match.group(1).lower()
        if mode in ("summarize", "action-items", "draft-reply", "auto"):
            return mode
    return DEFAULT_MODE


def analyze_email(mode: str, sender: str, to: str, cc: str, subject: str, body: str) -> str:
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": ANALYSIS_PROMPT.format(
            mode=mode, sender=sender, to=to, cc=cc, subject=subject, body=body
        )}],
    )
    return resp.choices[0].message.content


def handle_messages(inbox_id: str, agent_email: str):
    messages = agentmail.messages.list(inbox_id=inbox_id, labels=["unread"])
    for msg in messages.data:
        sender = msg.from_address or ""
        subject = msg.subject or ""
        body = msg.text or msg.html or ""
        to = ", ".join(msg.to) if msg.to else ""
        cc = ", ".join(msg.cc) if msg.cc else ""

        agentmail.messages.update(
            inbox_id=inbox_id,
            message_id=msg.id,
            remove_labels=["unread"],
        )

        mode = detect_mode(subject)
        analysis = analyze_email(mode, sender, to, cc, subject, body)

        agentmail.messages.send(
            inbox_id=inbox_id,
            to=[sender],
            subject=f"Re: {subject} [Agent Analysis]",
            text=f"Here is my {mode} analysis of the email thread:\n\n{analysis}\n\n---\nThis is a private reply from your email assistant ({agent_email}). Only you received this.",
            labels=["analysis", mode],
        )
        print(f"Analyzed email from {sender}: mode={mode}")


def main():
    inbox = agentmail.inboxes.create(display_name="CC Assistant")
    print(f"Assistant inbox: {inbox.email}")
    print(f"CC this address on emails to get instant analysis.")
    print(f"Default mode: {DEFAULT_MODE}\n")

    while True:
        handle_messages(inbox.id, inbox.email)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
