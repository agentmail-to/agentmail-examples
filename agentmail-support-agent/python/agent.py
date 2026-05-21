"""
AgentMail Support Agent — triage, respond, escalate, follow up, close.

Workflow:
  1. Create (or reuse) an AgentMail inbox.
  2. Poll for new mail every POLL_INTERVAL seconds.
  3. For each new email: ask Claude to call exactly one of respond / escalate
     / close_ticket. Optionally use web_search across HELP_CENTER_URL first.
     Tag the ticket with the classification.
  4. Once per cycle, scan tracked tickets and send a 48h follow-up to anyone
     waiting on us with no recent update.
  5. Append every action to tickets.csv for the support manager.

Run:
    pip install -r requirements.txt
    cp .env.example .env   # then fill in your keys
    python agent.py
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from pathlib import Path
from urllib.parse import urlparse

from agentmail import AgentMail
from agentmail.inboxes import CreateInboxRequest
from anthropic import Anthropic
from dotenv import load_dotenv

from prompt import build_system_prompt
from ticket_log import log_ticket

load_dotenv()

# --- config -------------------------------------------------------------------

AGENTMAIL_API_KEY = os.environ["AGENTMAIL_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
PRODUCT_NAME = os.getenv("PRODUCT_NAME", "the product")
AGENT_NAME = os.getenv("AGENT_NAME", "Sam")
ESCALATION_EMAIL = os.environ["ESCALATION_EMAIL"]
HELP_CENTER_URL = os.getenv("HELP_CENTER_URL", "").strip()
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))
FOLLOWUP_AFTER_HOURS = int(os.getenv("FOLLOWUP_AFTER_HOURS", "48"))
FOLLOWUP_COOLDOWN_HOURS = int(os.getenv("FOLLOWUP_COOLDOWN_HOURS", "24"))
INBOX_USERNAME = os.getenv("INBOX_USERNAME") or None

STATE_FILE = Path(".agent_state.json")

HELP_CENTER_DOMAIN = (
    urlparse(HELP_CENTER_URL).netloc if HELP_CENTER_URL else ""
)

CLASSIFICATIONS = ["billing", "bug", "feature_request", "general", "urgent"]

# --- clients ------------------------------------------------------------------

agentmail = AgentMail(api_key=AGENTMAIL_API_KEY)
claude = Anthropic(api_key=ANTHROPIC_API_KEY)


# --- Claude tools -------------------------------------------------------------


def _build_tools():
    tools = []
    if HELP_CENTER_DOMAIN:
        tools.append({
            "type": "web_search_20250305",
            "name": "web_search",
            "allowed_domains": [HELP_CENTER_DOMAIN],
            "max_uses": 3,
        })
    tools += [
        {
            "name": "respond",
            "description": "Reply to the customer with the answer. Use when the KB or web search has the info.",
            "input_schema": {
                "type": "object",
                "required": ["text", "classification"],
                "properties": {
                    "text": {"type": "string", "description": "The reply body, signed as instructed."},
                    "classification": {"type": "string", "enum": CLASSIFICATIONS},
                },
            },
        },
        {
            "name": "escalate",
            "description": "Forward to the human team when you can't answer or human approval is needed.",
            "input_schema": {
                "type": "object",
                "required": ["reason", "classification"],
                "properties": {
                    "reason": {"type": "string", "description": "One-sentence summary for the escalation team."},
                    "classification": {"type": "string", "enum": CLASSIFICATIONS},
                },
            },
        },
        {
            "name": "close_ticket",
            "description": "Send a brief friendly close when the customer signals they're done.",
            "input_schema": {
                "type": "object",
                "required": ["message", "classification"],
                "properties": {
                    "message": {"type": "string", "description": "Short closing message, signed."},
                    "classification": {"type": "string", "enum": CLASSIFICATIONS},
                },
            },
        },
    ]
    return tools


TOOLS = _build_tools()


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
    sender = getattr(message, "from_", None) or getattr(message, "from", None) or ""
    _, email = parseaddr(str(sender))
    return email.lower()


def get_or_create_inbox():
    state = load_state()
    if state.get("inbox_id"):
        try:
            return agentmail.inboxes.get(state["inbox_id"])
        except Exception as e:
            print(f"(stale state, creating new inbox: {e})")

    inbox = agentmail.inboxes.create(
        request=CreateInboxRequest(
            username=INBOX_USERNAME,
            display_name=f"{PRODUCT_NAME} support",
        )
    )
    state["inbox_id"] = inbox.inbox_id
    state["email"] = inbox.email
    save_state(state)
    return inbox


def thread_to_messages(thread, our_email: str):
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
            inbox_id, message_id,
            remove_labels=["unread"],
            add_labels=add_labels,
        )
    except Exception as e:
        print(f"  ! couldn't mark read: {e}")


# --- tool handlers ------------------------------------------------------------


def handle_respond(args, message, inbox):
    text = (args.get("text") or "").strip()
    classification = args.get("classification", "general")
    print(f"  💬 respond ({classification}, {len(text)} chars)")
    agentmail.inboxes.messages.reply(
        inbox.inbox_id, message.message_id, text=text
    )
    _mark_read(inbox.inbox_id, message.message_id, add_labels=[classification, "responded"])
    log_ticket(
        action="responded",
        classification=classification,
        sender=_sender_email(message),
        subject=message.subject or "",
        message_id=message.message_id,
        thread_id=message.thread_id,
        note=text[:200],
    )


def handle_escalate(args, message, inbox):
    reason = (args.get("reason") or "Unable to answer.").strip()
    classification = args.get("classification", "general")
    print(f"  ⚠️  escalate ({classification}): {reason}")
    try:
        agentmail.inboxes.messages.forward(
            inbox.inbox_id, message.message_id,
            to=[ESCALATION_EMAIL],
            text=f"[{classification.upper()}] {reason}",
        )
    except Exception as e:
        print(f"  ! escalation forward failed: {e}")

    ack = (
        f"Thanks for reaching out — I'm looping in our team to take a closer "
        f"look at this. We'll be in touch shortly."
    )
    agentmail.inboxes.messages.reply(
        inbox.inbox_id, message.message_id, text=ack
    )
    _mark_read(
        inbox.inbox_id, message.message_id,
        add_labels=[classification, "escalated", "awaiting_team"],
    )

    # Track for 48h follow-up
    state = load_state()
    state.setdefault("escalations", {})[message.thread_id] = {
        "escalated_at": datetime.now(timezone.utc).isoformat(),
        "last_followup_at": None,
        "classification": classification,
        "subject": message.subject or "",
        "sender": _sender_email(message),
        "message_id": message.message_id,
    }
    save_state(state)

    log_ticket(
        action="escalated",
        classification=classification,
        sender=_sender_email(message),
        subject=message.subject or "",
        message_id=message.message_id,
        thread_id=message.thread_id,
        note=reason,
    )


def handle_close_ticket(args, message, inbox):
    text = (args.get("message") or "Glad I could help — closing this out.").strip()
    classification = args.get("classification", "general")
    print(f"  ✅ close_ticket ({classification})")
    agentmail.inboxes.messages.reply(
        inbox.inbox_id, message.message_id, text=text
    )
    _mark_read(inbox.inbox_id, message.message_id, add_labels=[classification, "closed"])

    # Stop tracking for follow-up
    state = load_state()
    state.get("escalations", {}).pop(message.thread_id, None)
    save_state(state)

    log_ticket(
        action="closed",
        classification=classification,
        sender=_sender_email(message),
        subject=message.subject or "",
        message_id=message.message_id,
        thread_id=message.thread_id,
        note=text[:200],
    )


TOOL_HANDLERS = {
    "respond": handle_respond,
    "escalate": handle_escalate,
    "close_ticket": handle_close_ticket,
}


# --- core processing ----------------------------------------------------------


def process_message(message, inbox):
    print(f"  → fetching thread {message.thread_id}")
    thread = agentmail.inboxes.threads.get(inbox.inbox_id, message.thread_id)

    if thread.messages and _sender_email(thread.messages[-1]) == inbox.email.lower():
        if message.message_id != thread.messages[-1].message_id:
            print("  → thread already replied; skipping")
            _mark_read(inbox.inbox_id, message.message_id)
            return

    conversation = thread_to_messages(thread, inbox.email)
    if not conversation or conversation[-1]["role"] != "user":
        print("  ! no user content to act on")
        _mark_read(inbox.inbox_id, message.message_id)
        return

    system_prompt = build_system_prompt(inbox_email=inbox.email)

    print(f"  → asking Claude (model={MODEL}{', web_search → ' + HELP_CENTER_DOMAIN if HELP_CENTER_DOMAIN else ''})")
    response = claude.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system_prompt,
        tools=TOOLS,
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
        print("  ! Claude did not call any action tool")
        _mark_read(inbox.inbox_id, message.message_id)


# --- 48h follow-up ------------------------------------------------------------


def maybe_send_followups(inbox):
    state = load_state()
    escalations = state.get("escalations", {})
    if not escalations:
        return

    now = datetime.now(timezone.utc)
    stale_threshold = now - timedelta(hours=FOLLOWUP_AFTER_HOURS)
    cooldown_threshold = now - timedelta(hours=FOLLOWUP_COOLDOWN_HOURS)

    sent = 0
    for thread_id, info in list(escalations.items()):
        try:
            escalated_at = datetime.fromisoformat(info["escalated_at"])
            last_fu = info.get("last_followup_at")
            last_fu_dt = datetime.fromisoformat(last_fu) if last_fu else None

            # Need: ticket older than threshold, AND no follow-up recently
            if escalated_at > stale_threshold:
                continue
            if last_fu_dt and last_fu_dt > cooldown_threshold:
                continue

            print(f"  📨 sending 48h follow-up on thread {thread_id[:8]}...")
            agentmail.inboxes.messages.reply(
                inbox.inbox_id, info["message_id"],
                text=(
                    "Quick update — wanted to let you know this is still on our "
                    "team's radar. We're working through it and will follow up as "
                    "soon as we have an answer. Apologies for the wait.\n\n"
                    f"{AGENT_NAME}, Support Team"
                ),
            )

            info["last_followup_at"] = now.isoformat()
            sent += 1

            log_ticket(
                action="followed_up",
                classification=info.get("classification", "general"),
                sender=info.get("sender", ""),
                subject=info.get("subject", ""),
                message_id=info["message_id"],
                thread_id=thread_id,
                note=f"Follow-up sent {FOLLOWUP_AFTER_HOURS}h after escalation",
            )
        except Exception as e:
            print(f"  ! follow-up failed for {thread_id}: {e}")

    if sent:
        save_state(state)


# --- main loop ----------------------------------------------------------------


def main():
    inbox = get_or_create_inbox()
    print(f"\n📬 Support agent live at: {inbox.email}")
    if HELP_CENTER_DOMAIN:
        print(f"   Web search: {HELP_CENTER_URL}")
    print(f"   Escalating to: {ESCALATION_EMAIL}")
    print(f"   Follow-up: {FOLLOWUP_AFTER_HOURS}h after escalation, max once per {FOLLOWUP_COOLDOWN_HOURS}h")
    print(f"   Polling every {POLL_INTERVAL}s. Ctrl-C to stop.\n")

    seen: set[str] = set()
    while True:
        try:
            resp = agentmail.inboxes.messages.list(
                inbox.inbox_id, labels=["unread"]
            )
            new_msgs = [m for m in (resp.messages or []) if m.message_id not in seen]
            for m in new_msgs:
                seen.add(m.message_id)
                if _sender_email(m) == inbox.email.lower():
                    continue
                print(f"\n📩 from {_sender_email(m)}: {(m.subject or '(no subject)')[:60]}")
                try:
                    process_message(m, inbox)
                except Exception as e:
                    print(f"  ! error processing message: {e}")

            maybe_send_followups(inbox)

        except Exception as e:
            print(f"poll error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
