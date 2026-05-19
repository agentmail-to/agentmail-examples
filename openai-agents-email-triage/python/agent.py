"""
Email Triage Agent — built with OpenAI Agents SDK + AgentMail.

Gives an autonomous agent its own email inbox. The agent reads incoming
messages, classifies them, drafts replies, and either sends them directly
or escalates to a human depending on confidence.

Run:
    pip install -r requirements.txt
    cp .env.example .env   # fill in your keys
    python agent.py
"""

import json
import os
import time
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path

from agentmail import AgentMail
from agentmail.inboxes import CreateInboxRequest
from agents import Agent, Runner, function_tool
from dotenv import load_dotenv

load_dotenv()

# --- config -------------------------------------------------------------------

AGENTMAIL_API_KEY = os.environ["AGENTMAIL_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
ESCALATION_EMAIL = os.environ["ESCALATION_EMAIL"]
PRODUCT_NAME = os.getenv("PRODUCT_NAME", "Acme Corp")
AGENT_NAME = os.getenv("AGENT_NAME", "Alex")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))
INBOX_USERNAME = os.getenv("INBOX_USERNAME") or None

STATE_FILE = Path(".agent_state.json")

CATEGORIES = ["billing", "bug_report", "feature_request", "question", "spam", "urgent"]

# --- clients ------------------------------------------------------------------

mail = AgentMail(api_key=AGENTMAIL_API_KEY)


# --- state management ---------------------------------------------------------


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


# --- helpers ------------------------------------------------------------------


def sender_email(message) -> str:
    sender = getattr(message, "from_", None) or getattr(message, "from", None) or ""
    _, email = parseaddr(str(sender))
    return email.lower()


def get_or_create_inbox():
    state = load_state()
    if state.get("inbox_id"):
        try:
            return mail.inboxes.get(state["inbox_id"])
        except Exception as e:
            print(f"(stale inbox, creating new: {e})")

    inbox = mail.inboxes.create(
        request=CreateInboxRequest(
            username=INBOX_USERNAME,
            display_name=f"{PRODUCT_NAME} Triage",
        )
    )
    state["inbox_id"] = inbox.inbox_id
    state["email"] = inbox.email
    save_state(state)
    return inbox


def build_thread_context(thread, our_email: str) -> str:
    """Convert an AgentMail thread into a readable conversation transcript."""
    our_email = our_email.lower()
    lines = []
    for m in thread.messages or []:
        who = sender_email(m)
        role = "Agent" if who == our_email else f"Customer ({who})"
        body = (getattr(m, "extracted_text", None) or m.text or "").strip()
        if body:
            lines.append(f"[{role}]:\n{body}")
    return "\n\n---\n\n".join(lines) if lines else "(empty thread)"


# --- tools (called by the OpenAI agent) --------------------------------------


@function_tool
def reply_to_email(
    inbox_id: str, message_id: str, text: str, category: str
) -> str:
    """Send a reply to an email and label it.

    Args:
        inbox_id: The inbox ID.
        message_id: The message ID to reply to.
        text: The reply body.
        category: One of: billing, bug_report, feature_request, question, spam, urgent.
    """
    mail.inboxes.messages.reply(inbox_id, message_id, text=text)
    try:
        mail.inboxes.messages.update(
            inbox_id, message_id,
            remove_labels=["unread"],
            add_labels=[category, "auto-replied"],
        )
    except Exception:
        pass
    return f"Reply sent and labeled as '{category}'."


@function_tool
def escalate_to_human(
    inbox_id: str, message_id: str, reason: str, category: str
) -> str:
    """Forward an email to the human team when the agent can't confidently respond.

    Args:
        inbox_id: The inbox ID.
        message_id: The message ID to escalate.
        reason: A brief explanation of why this needs human attention.
        category: One of: billing, bug_report, feature_request, question, spam, urgent.
    """
    mail.inboxes.messages.forward(
        inbox_id, message_id,
        to=[ESCALATION_EMAIL],
        text=f"[{category.upper()} — ESCALATION] {reason}",
    )
    # Send a holding reply to the customer
    mail.inboxes.messages.reply(
        inbox_id, message_id,
        text=(
            "Thanks for reaching out. I've flagged this for our team and "
            "someone will follow up with you shortly."
        ),
    )
    try:
        mail.inboxes.messages.update(
            inbox_id, message_id,
            remove_labels=["unread"],
            add_labels=[category, "escalated"],
        )
    except Exception:
        pass
    return f"Escalated to human team. Category: {category}. Reason: {reason}"


@function_tool
def skip_message(inbox_id: str, message_id: str, reason: str) -> str:
    """Skip a message (e.g., spam, auto-reply, or not actionable).

    Args:
        inbox_id: The inbox ID.
        message_id: The message to skip.
        reason: Why this message is being skipped.
    """
    try:
        mail.inboxes.messages.update(
            inbox_id, message_id,
            remove_labels=["unread"],
            add_labels=["skipped"],
        )
    except Exception:
        pass
    return f"Message skipped: {reason}"


@function_tool
def create_draft(
    inbox_id: str, to: str, subject: str, text: str
) -> str:
    """Create a draft email for human review before sending.

    Args:
        inbox_id: The inbox ID.
        to: Recipient email address.
        subject: Email subject line.
        text: Draft body text.
    """
    draft = mail.inboxes.drafts.create(
        inbox_id, to=[to], subject=subject, text=text
    )
    return f"Draft created (id: {draft.draft_id}). A human can review and send it."


# --- agent definition ---------------------------------------------------------


SYSTEM_PROMPT = f"""You are {AGENT_NAME}, an email triage agent for {PRODUCT_NAME}.

Your job is to process incoming emails in the agent's inbox. For each email:

1. Read the full conversation thread for context.
2. Classify the email into one of these categories: {', '.join(CATEGORIES)}.
3. Decide on an action:
   - **reply_to_email**: You're confident you can answer. Write a helpful, concise reply.
   - **escalate_to_human**: The question is complex, sensitive, or you're unsure. Forward it.
   - **skip_message**: It's spam, an auto-reply, or a no-reply address.
   - **create_draft**: You have a good reply but want a human to review it first.

Guidelines:
- Be helpful, professional, and concise.
- Sign replies as "{AGENT_NAME}, {PRODUCT_NAME} Support".
- Never promise things you can't verify (refunds, SLAs, etc.) — escalate those.
- For billing and urgent issues, prefer escalation.
- For spam or auto-generated messages, skip them.
- When replying, reference specifics from the customer's message.
"""

triage_agent = Agent(
    name="EmailTriageAgent",
    instructions=SYSTEM_PROMPT,
    model=MODEL,
    tools=[reply_to_email, escalate_to_human, skip_message, create_draft],
)


# --- main loop ----------------------------------------------------------------


def process_message(message, inbox):
    """Hand a single unread message to the agent for triage."""
    print(f"  → fetching thread {message.thread_id}")
    thread = mail.inboxes.threads.get(inbox.inbox_id, message.thread_id)
    context = build_thread_context(thread, inbox.email)

    prompt = (
        f"New email in inbox {inbox.inbox_id}.\n"
        f"Message ID: {message.message_id}\n"
        f"From: {sender_email(message)}\n"
        f"Subject: {message.subject or '(no subject)'}\n"
        f"Date: {getattr(message, 'date', 'unknown')}\n\n"
        f"--- Thread ---\n{context}\n\n"
        f"Triage this email. Use exactly one tool."
    )

    result = Runner.run_sync(triage_agent, prompt)
    print(f"  ✓ agent output: {result.final_output[:120]}...")


def main():
    inbox = get_or_create_inbox()
    print(f"\n📬 Email triage agent live at: {inbox.email}")
    print(f"   Escalating to: {ESCALATION_EMAIL}")
    print(f"   Model: {MODEL}")
    print(f"   Polling every {POLL_INTERVAL}s. Ctrl-C to stop.\n")

    seen: set[str] = set()
    while True:
        try:
            resp = mail.inboxes.messages.list(inbox.inbox_id, labels=["unread"])
            new_msgs = [m for m in (resp.messages or []) if m.message_id not in seen]
            for m in new_msgs:
                seen.add(m.message_id)
                if sender_email(m) == inbox.email.lower():
                    continue
                print(
                    f"\n📩 from {sender_email(m)}: "
                    f"{(m.subject or '(no subject)')[:60]}"
                )
                try:
                    process_message(m, inbox)
                except Exception as e:
                    print(f"  ! error processing: {e}")
        except Exception as e:
            print(f"poll error: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
