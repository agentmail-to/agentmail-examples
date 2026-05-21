"""
AgentMail Inbox Zero Agent — drafts replies while you sleep.

Workflow:
  1. Create (or reuse) an AgentMail inbox.
  2. Poll for new mail every POLL_INTERVAL seconds.
  3. For each new email: ask Claude to classify and either draft a reply,
     flag for human, or mark handled.
  4. Once per day at WAKE_TIME, email USER_EMAIL a digest of overnight activity.

Run:
    pip install -r requirements.txt
    cp .env.example .env   # then fill in your keys
    python agent.py
"""

import json
import os
import time
from datetime import datetime
from email.utils import parseaddr
from pathlib import Path

from agentmail import AgentMail
from agentmail.inboxes import CreateInboxRequest
from anthropic import Anthropic
from dotenv import load_dotenv

from digest import build_digest_text, is_digest_due
from prompt import build_system_prompt

load_dotenv()

# --- config -------------------------------------------------------------------

AGENTMAIL_API_KEY = os.environ["AGENTMAIL_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
USER_NAME = os.getenv("USER_NAME", "the user")
USER_EMAIL = os.environ["USER_EMAIL"]
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "20"))
WAKE_TIME = os.getenv("WAKE_TIME", "08:00")
INBOX_USERNAME = os.getenv("INBOX_USERNAME") or None

STATE_FILE = Path(".agent_state.json")

# --- clients ------------------------------------------------------------------

agentmail = AgentMail(api_key=AGENTMAIL_API_KEY)
claude = Anthropic(api_key=ANTHROPIC_API_KEY)


# --- Claude tools -------------------------------------------------------------

TOOLS = [
    {
        "name": "draft_reply",
        "description": (
            "Save a draft reply to the source email. The draft lands in the "
            "drafts folder for the user to review and send manually. Use for "
            "emails that need a substantive response."
        ),
        "input_schema": {
            "type": "object",
            "required": ["text"],
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The body of the reply, in the user's voice. Plain text only.",
                },
            },
        },
    },
    {
        "name": "flag_for_human",
        "description": (
            "Mark the email as needing the user's attention without drafting "
            "a reply. Use when the email needs a decision, commitment, or "
            "sensitive judgment that should not be auto-drafted."
        ),
        "input_schema": {
            "type": "object",
            "required": ["reason"],
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "One sentence on why this needs human attention (shown in the morning digest).",
                },
            },
        },
    },
    {
        "name": "mark_handled",
        "description": (
            "Mark the email as handled — no draft, no flag. Use for spam, "
            "promotional, FYI, or auto-notifications the user does not need to act on."
        ),
        "input_schema": {
            "type": "object",
            "required": ["category"],
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["fyi", "spam", "promotional", "auto_notification"],
                    "description": "Why this email doesn't need action.",
                },
                "note": {
                    "type": "string",
                    "description": "Optional one-line context.",
                },
            },
        },
    },
]


# --- state --------------------------------------------------------------------


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


def _sender_email(message) -> str:
    """Extract bare email from a message's `from` field (e.g. 'Name <a@b.com>')."""
    sender = getattr(message, "from_", None) or getattr(message, "from", None) or ""
    _, email = parseaddr(str(sender))
    return email.lower()


def get_or_create_inbox():
    """Reuse the inbox from state, otherwise create a fresh one."""
    state = load_state()
    inbox_id = state.get("inbox_id")
    if inbox_id:
        try:
            return agentmail.inboxes.get(inbox_id)
        except Exception as e:
            print(f"(stale state, creating new inbox: {e})")

    inbox = agentmail.inboxes.create(
        request=CreateInboxRequest(
            username=INBOX_USERNAME,
            display_name=f"{USER_NAME}'s inbox-zero agent",
        )
    )
    state["inbox_id"] = inbox.inbox_id
    state["email"] = inbox.email
    save_state(state)
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

    while msgs and msgs[0]["role"] == "assistant":
        msgs.pop(0)

    collapsed = []
    for m in msgs:
        if collapsed and collapsed[-1]["role"] == m["role"]:
            collapsed[-1]["content"] += "\n\n" + m["content"]
        else:
            collapsed.append(m)
    return collapsed


def _mark_read(inbox_id: str, message_id: str, add_labels=None) -> None:
    try:
        agentmail.inboxes.messages.update(
            inbox_id,
            message_id,
            remove_labels=["unread"],
            add_labels=add_labels,
        )
    except Exception as e:
        print(f"  ! couldn't mark read: {e}")


# --- tool handlers ------------------------------------------------------------


def handle_draft_reply(args, message, inbox):
    text = args.get("text", "").strip()
    if not text:
        print("  ! draft_reply called with empty text, skipping")
        return
    requester = _sender_email(message)
    subject = message.subject or "(no subject)"
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    draft = agentmail.inboxes.drafts.create(
        inbox_id=inbox.inbox_id,
        in_reply_to=message.message_id,
        to=[requester] if requester else None,
        subject=subject,
        text=text,
    )
    print(f"  📝 draft saved: {draft.draft_id} → {requester}")
    _mark_read(inbox.inbox_id, message.message_id, add_labels=["drafted"])


def handle_flag_for_human(args, message, inbox):
    reason = args.get("reason", "").strip()
    print(f"  ⚠️  flagged for human: {reason}")
    _mark_read(inbox.inbox_id, message.message_id, add_labels=["needs_human"])


def handle_mark_handled(args, message, inbox):
    category = args.get("category", "fyi")
    note = (args.get("note") or "").strip()
    print(f"  ✓ handled as {category}{f' — {note}' if note else ''}")
    _mark_read(inbox.inbox_id, message.message_id, add_labels=[category])


TOOL_HANDLERS = {
    "draft_reply": handle_draft_reply,
    "flag_for_human": handle_flag_for_human,
    "mark_handled": handle_mark_handled,
}


# --- core processing ----------------------------------------------------------


def process_message(message, inbox):
    """Send the message + thread to Claude, dispatch the chosen tool."""
    print(f"  → fetching thread {message.thread_id}")
    thread = agentmail.inboxes.threads.get(inbox.inbox_id, message.thread_id)

    # Skip if already replied (someone else's automation, or our prior reply)
    if thread.messages and _sender_email(thread.messages[-1]) == inbox.email.lower():
        if message.message_id != thread.messages[-1].message_id:
            print("  → thread already handled; marking read and skipping")
            _mark_read(inbox.inbox_id, message.message_id)
            return

    conversation = thread_to_messages(thread, inbox.email)
    if not conversation or conversation[-1]["role"] != "user":
        print("  ! no user content to act on, marking read")
        _mark_read(inbox.inbox_id, message.message_id)
        return

    system_prompt = build_system_prompt(inbox_email=inbox.email)

    print(f"  → asking Claude (model={MODEL}, {len(conversation)} turn(s))")
    response = claude.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system_prompt,
        tools=TOOLS,
        tool_choice={"type": "any"},  # force a tool call
        messages=conversation,
    )

    handled = False
    for block in response.content:
        if block.type == "tool_use" and block.name in TOOL_HANDLERS:
            try:
                TOOL_HANDLERS[block.name](block.input, message, inbox)
                handled = True
            except Exception as e:
                print(f"  ! tool handler {block.name} failed: {e}")

    if not handled:
        print("  ! Claude did not call any tool, marking read defensively")
        _mark_read(inbox.inbox_id, message.message_id)


# --- digest -------------------------------------------------------------------


def maybe_send_digest(inbox):
    state = load_state()
    if not is_digest_due(WAKE_TIME, state.get("last_digest_date")):
        return

    print(f"\n📨 Sending morning digest to {USER_EMAIL}…")

    # All drafts created since last digest (default: last 24h if first run)
    drafts_resp = agentmail.inboxes.drafts.list(inbox.inbox_id)
    drafts = drafts_resp.drafts or []

    flagged_resp = agentmail.inboxes.messages.list(
        inbox.inbox_id, labels=["needs_human"]
    )
    flagged = flagged_resp.messages or []

    body = build_digest_text(USER_NAME, drafts, flagged, inbox.email)
    today_str = datetime.now().strftime("%A, %B %d")

    agentmail.inboxes.messages.send(
        inbox_id=inbox.inbox_id,
        to=[USER_EMAIL],
        subject=f"Inbox digest — {today_str}",
        text=body,
    )

    state["last_digest_date"] = datetime.now().strftime("%Y-%m-%d")
    save_state(state)
    print(f"   sent ({len(drafts)} draft(s), {len(flagged)} flagged)\n")


# --- main loop ----------------------------------------------------------------


def main():
    inbox = get_or_create_inbox()
    print(f"\n📬 Inbox-zero agent live at: {inbox.email}")
    print(f"   Forward mail there to test it.")
    print(f"   Polling every {POLL_INTERVAL}s. Morning digest at {WAKE_TIME} → {USER_EMAIL}.")
    print(f"   Ctrl-C to stop.\n")

    seen: set[str] = set()

    while True:
        try:
            resp = agentmail.inboxes.messages.list(
                inbox.inbox_id, labels=["unread"]
            )
            new_msgs = [
                m for m in (resp.messages or []) if m.message_id not in seen
            ]

            for m in new_msgs:
                seen.add(m.message_id)
                if _sender_email(m) == inbox.email.lower():
                    continue  # skip our own outgoing mail
                print(f"\n📩 from {_sender_email(m)}: {(m.subject or '(no subject)')[:60]}")
                try:
                    process_message(m, inbox)
                except Exception as e:
                    print(f"  ! error processing message: {e}")

            maybe_send_digest(inbox)

        except Exception as e:
            print(f"poll error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
