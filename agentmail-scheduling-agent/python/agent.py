"""
AgentMail Scheduling Agent — minimal polling loop template.

Workflow:
  1. Create (or reuse) an AgentMail inbox.
  2. Poll for new messages every POLL_INTERVAL seconds.
  3. For each new message: fetch the full thread, send it to Claude with the
     scheduling system prompt, and reply in the same thread.

Run:
    pip install -r requirements.txt
    cp .env.example .env   # then fill in your keys
    python agent.py
"""

import json
import os
import time
from email.utils import parseaddr
from pathlib import Path

from agentmail import AgentMail
from agentmail.inboxes import CreateInboxRequest
from anthropic import Anthropic
from dotenv import load_dotenv

from calendar_invite import build_ics, ics_attachment
from prompt import build_system_prompt

# Tool exposed to Claude. When Claude calls this, our code generates an .ics
# file and attaches it to the outgoing reply — no calendar OAuth needed.
CONFIRM_MEETING_TOOL = {
    "name": "confirm_meeting",
    "description": (
        "Call this when the requester has confirmed a specific date and time. "
        "It generates a calendar invite (.ics) and attaches it to your reply "
        "so the requester can add the meeting to their calendar in one click."
    ),
    "input_schema": {
        "type": "object",
        "required": ["title", "start_iso", "duration_minutes"],
        "properties": {
            "title": {
                "type": "string",
                "description": "Subject of the meeting, e.g. 'Intro call'",
            },
            "start_iso": {
                "type": "string",
                "description": (
                    "ISO 8601 start datetime with timezone offset, e.g. "
                    "'2026-05-04T10:00:00-07:00'. Always include the offset."
                ),
            },
            "duration_minutes": {
                "type": "integer",
                "description": "Meeting length in minutes (e.g. 30, 60).",
            },
        },
    },
}

load_dotenv()

# --- config -------------------------------------------------------------------

AGENTMAIL_API_KEY = os.environ["AGENTMAIL_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
USER_NAME = os.getenv("USER_NAME", "the user")
USER_EMAIL = os.environ["USER_EMAIL"]
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))
INBOX_USERNAME = os.getenv("INBOX_USERNAME") or None  # optional, else random

STATE_FILE = Path(".agent_state.json")

# --- clients ------------------------------------------------------------------

agentmail = AgentMail(api_key=AGENTMAIL_API_KEY)
claude = Anthropic(api_key=ANTHROPIC_API_KEY)


# --- helpers ------------------------------------------------------------------


def _sender_email(message) -> str:
    """Extract the bare email from a message's `from` field.

    The SDK exposes `from` as `from_` (Python keyword) and the value is a
    string formatted like `'Display Name <user@domain.com>'`. We strip the
    display-name part so we can compare against `inbox.email` safely.
    """
    sender = getattr(message, "from_", None) or getattr(message, "from", None) or ""
    _, email = parseaddr(str(sender))
    return email.lower()


def get_or_create_inbox():
    """Reuse the inbox saved in state, otherwise create a fresh one."""
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
            inbox_id = state.get("inbox_id")
            if inbox_id:
                return agentmail.inboxes.get(inbox_id)
        except Exception as e:
            print(f"(stale state, creating new inbox: {e})")

    inbox = agentmail.inboxes.create(
        request=CreateInboxRequest(
            username=INBOX_USERNAME,
            display_name=f"{USER_NAME}'s scheduling agent",
        )
    )
    STATE_FILE.write_text(
        json.dumps({"inbox_id": inbox.inbox_id, "email": inbox.email}, indent=2)
    )
    return inbox


def thread_to_messages(thread, our_email: str):
    """Convert an AgentMail thread into Anthropic-shaped messages."""
    our_email = our_email.lower()
    msgs = []
    for m in thread.messages or []:
        sender = _sender_email(m)
        role = "assistant" if sender == our_email else "user"
        body = (getattr(m, "extracted_text", None) or m.text or "").strip()
        if body:
            msgs.append({"role": role, "content": body})

    # Anthropic requires the first message to be from the user
    while msgs and msgs[0]["role"] == "assistant":
        msgs.pop(0)

    # Anthropic disallows consecutive same-role messages — collapse them
    collapsed = []
    for m in msgs:
        if collapsed and collapsed[-1]["role"] == m["role"]:
            collapsed[-1]["content"] += "\n\n" + m["content"]
        else:
            collapsed.append(m)
    return collapsed


def _mark_read(inbox_id: str, message_id: str) -> None:
    try:
        agentmail.inboxes.messages.update(
            inbox_id, message_id, remove_labels=["unread"]
        )
    except Exception as e:
        print(f"  ! couldn't mark read: {e}")


def process_message(message, inbox):
    """Fetch the thread, send it to Claude, reply in-thread with the answer."""
    print(f"  → fetching thread {message.thread_id}")
    thread = agentmail.inboxes.threads.get(inbox.inbox_id, message.thread_id)

    # If the thread's most recent message is from us, this message has already
    # been superseded by a newer reply. Mark it read and move on.
    if thread.messages and _sender_email(thread.messages[-1]) == inbox.email.lower():
        if message.message_id != thread.messages[-1].message_id:
            print("  → thread already replied; marking read and skipping")
            _mark_read(inbox.inbox_id, message.message_id)
            return

    conversation = thread_to_messages(thread, inbox.email)
    if not conversation:
        print("  ! empty conversation, skipping")
        _mark_read(inbox.inbox_id, message.message_id)
        return

    # Defensive: Anthropic requires the conversation to end with a user turn.
    if conversation[-1]["role"] != "user":
        print("  ! conversation does not end with user turn; skipping")
        _mark_read(inbox.inbox_id, message.message_id)
        return

    system_prompt = build_system_prompt(inbox_email=inbox.email)

    print(f"  → asking Claude (model={MODEL}, {len(conversation)} turn(s))")
    response = claude.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system_prompt,
        tools=[CONFIRM_MEETING_TOOL],
        messages=conversation,
    )

    # Claude's response can have multiple content blocks: text (the email body)
    # and tool_use (the structured meeting confirmation, if applicable).
    text_parts = []
    invite_args = None
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use" and block.name == "confirm_meeting":
            invite_args = block.input
    reply_text = "\n\n".join(text_parts).strip() or "Looking forward to it."

    # If Claude confirmed a slot, build a calendar invite and attach it.
    requester = _sender_email(message)
    attachments = None
    if invite_args:
        attendees = [requester]
        if USER_EMAIL.lower() != requester:
            attendees.append(USER_EMAIL.lower())
        ics = build_ics(
            title=invite_args["title"],
            start_iso=invite_args["start_iso"],
            duration_minutes=int(invite_args.get("duration_minutes", 30)),
            organizer_email=inbox.email,
            attendees=attendees,
            description=f"Scheduled by {USER_NAME}'s scheduling agent.",
        )
        attachments = [ics_attachment(ics)]

    # CC the user on every outgoing reply so they see the conversation in real
    # time. Skip cc if it would land back in the requester's own inbox.
    cc = USER_EMAIL if USER_EMAIL.lower() != requester else None

    extras = []
    if cc:
        extras.append(f"cc={cc}")
    if attachments:
        extras.append("invite=attached")
    print(
        f"  → replying ({len(reply_text)} chars"
        + (f", {', '.join(extras)}" if extras else "")
        + ")"
    )
    agentmail.inboxes.messages.reply(
        inbox.inbox_id,
        message.message_id,
        text=reply_text,
        cc=cc,
        attachments=attachments,
    )
    _mark_read(inbox.inbox_id, message.message_id)


# --- main loop ----------------------------------------------------------------


def main():
    inbox = get_or_create_inbox()
    print(f"\n📬 Scheduling agent live at: {inbox.email}")
    print(f"   Send an email to that address to test it.")
    print(f"   Polling every {POLL_INTERVAL}s. Ctrl-C to stop.\n")

    # Defensive: in-process dedup against re-processing if mark-as-read ever fails.
    seen: set[str] = set()

    while True:
        try:
            # Pull only unread mail. Marking-as-read after each reply keeps this small.
            resp = agentmail.inboxes.messages.list(
                inbox.inbox_id, labels=["unread"]
            )
            new_msgs = [
                m for m in (resp.messages or []) if m.message_id not in seen
            ]

            for m in new_msgs:
                seen.add(m.message_id)
                if _sender_email(m) == inbox.email.lower():
                    continue  # safety net — sent mail shouldn't have `unread`
                print(f"\n📩 from {_sender_email(m)}: {(m.subject or '(no subject)')[:60]}")
                try:
                    process_message(m, inbox)
                except Exception as e:
                    print(f"  ! error processing message: {e}")

        except Exception as e:
            print(f"poll error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
