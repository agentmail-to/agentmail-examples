"""
AgentMail Approval Inbox — extract structured requests, get one-reply approval, fire actions.

Per incoming email:
  1. Is this a reply on a thread that has a pending request? → parse the user's
     decision (approve/decline/defer/changes), update requests.csv, fire the
     configured side-effect actions, ack the user.
  2. Otherwise: classify with Claude using approval_types.yaml. Either:
       - extract_request(type, fields, summary) → save row to requests.csv,
         email the user a clean review with one-line approve/decline prompt
       - discard(reason) → mark read, no reply

Side-effect actions per type (configured in approval_types.yaml):
  forward_to:      email — forwards the original email
  webhook:         URL — POSTs the request JSON
  reply_to_sender: string — replies on the original sender's thread (with
                   {field_name} interpolation)

Run:
    pip install -r requirements.txt
    cp .env.example .env
    cp approval_types.example.yaml approval_types.yaml   # edit with your types
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
from anthropic import Anthropic
from dotenv import load_dotenv

import actions as actions_mod
import reply_parser
import requests_store
import types_config
from prompt import build_classify_prompt

load_dotenv()

# --- config -------------------------------------------------------------------

AGENTMAIL_API_KEY = os.environ["AGENTMAIL_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
USER_NAME = os.getenv("USER_NAME", "User")
USER_EMAIL = os.environ["USER_EMAIL"]
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "15"))
INBOX_USERNAME = os.getenv("INBOX_USERNAME") or None

STATE_FILE = Path(".agent_state.json")

# --- clients ------------------------------------------------------------------

agentmail = AgentMail(api_key=AGENTMAIL_API_KEY)
claude = Anthropic(api_key=ANTHROPIC_API_KEY)

# --- Claude tools -------------------------------------------------------------

EXTRACT_REQUEST_TOOL = {
    "name": "extract_request",
    "description": "Email matches one of the configured request types. Extract the fields the type wants and summarize.",
    "input_schema": {
        "type": "object",
        "required": ["type", "fields", "summary"],
        "properties": {
            "type": {"type": "string", "description": "The matched type name. Must exactly match one of the configured type names."},
            "fields": {
                "type": "object",
                "description": "Object with extracted fields. Keys must match the type's `fields to extract` list. Use empty string for fields that aren't extractable.",
                "additionalProperties": {"type": "string"},
            },
            "summary": {"type": "string", "description": "Single-line ≤100 char description (e.g. 'Acme Corp invoice $4,200 due May 15')."},
        },
    },
}

DISCARD_TOOL = {
    "name": "discard",
    "description": "Email does NOT match any configured request type. Newsletter / internal / marketing / off-topic.",
    "input_schema": {
        "type": "object",
        "required": ["reason"],
        "properties": {"reason": {"type": "string"}},
    },
}

CLASSIFY_TOOLS = [EXTRACT_REQUEST_TOOL, DISCARD_TOOL]


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
            display_name=f"{USER_NAME} Approvals",
        )
    )
    state["inbox_id"] = inbox.inbox_id
    state["email"] = inbox.email
    save_state(state)
    return inbox


def _mark_read(inbox_id: str, message_id: str, add_labels=None) -> None:
    try:
        agentmail.inboxes.messages.update(
            inbox_id, message_id,
            remove_labels=["unread"],
            add_labels=add_labels,
        )
    except Exception as e:
        print(f"  ! couldn't mark read: {e}")


# --- formatting ---------------------------------------------------------------


def _format_review_email(request_row: dict, fields: dict, type_cfg) -> str:
    """The review email sent to the user — what they reply 'approve' to."""
    lines = [
        f"[{request_row['type']}] {request_row['summary']}",
        "",
    ]
    for k in type_cfg.extract_fields:
        v = fields.get(k, "") or "(not extracted)"
        lines.append(f"  {k}: {v}")
    lines.append("")

    # Document what each decision will trigger
    approve_actions = []
    if type_cfg.approve.get("forward_to"):
        approve_actions.append(f"forward to {type_cfg.approve['forward_to']}")
    if type_cfg.approve.get("webhook"):
        approve_actions.append("fire webhook")
    if type_cfg.approve.get("reply_to_sender"):
        approve_actions.append("reply to original sender")
    if not approve_actions:
        approve_actions.append("just record decision")

    decline_actions = []
    if type_cfg.decline.get("forward_to"):
        decline_actions.append(f"forward to {type_cfg.decline['forward_to']}")
    if type_cfg.decline.get("webhook"):
        decline_actions.append("fire webhook")
    if type_cfg.decline.get("reply_to_sender"):
        decline_actions.append("reply to original sender")
    if not decline_actions:
        decline_actions.append("just record decision")

    lines += [
        "Reply with one word to decide:",
        f"  approve   → {', '.join(approve_actions)}",
        f"  decline   → {', '.join(decline_actions)}",
        f"  defer 7d  → snooze, ask again later",
        f"  edit: <text>  → request changes",
        "",
        f"Request id: {request_row['id']}",
        "",
        "— Approval inbox",
    ]
    return "\n".join(lines)


def _format_decision_ack(decision: str, request_row: dict, confirmations: list[str]) -> str:
    return (
        f"Recorded {decision.upper()} for [{request_row['type']}] {request_row['summary']}.\n\n"
        f"Actions taken:\n"
        + "\n".join(f"  • {c}" for c in confirmations)
        + f"\n\nRequest id: {request_row['id']}\n\n— Approval inbox"
    )


# --- core processing ----------------------------------------------------------


def process_message(message, inbox, types):
    full = agentmail.inboxes.messages.get(inbox.inbox_id, message.message_id)
    extracted = (getattr(full, "extracted_text", None) or "").strip()
    raw = (full.text or "").strip()
    body = raw if len(raw) > len(extracted) * 1.5 else (extracted or raw)

    sender = _sender_email(message)
    subject = getattr(message, "subject", "") or ""
    thread_id = getattr(full, "thread_id", "") or ""
    print(f"  → {sender}  ·  '{subject[:60]}'  ·  thread {thread_id[:24]}")

    # Skip our own outgoing replies
    if sender == inbox.email.lower():
        print("  · skipping our own outgoing reply")
        _mark_read(inbox.inbox_id, message.message_id)
        return

    # 1. Is this a reply on a thread with a pending request?
    pending = requests_store.find_pending_by_thread(thread_id)
    if pending:
        return _handle_decision_reply(message, pending, body, types, inbox)

    # 2. Else classify with Claude
    if not types:
        print("  ! no types configured (approval_types.yaml empty/missing) — discarding")
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["unconfigured"])
        return

    response = claude.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=build_classify_prompt(inbox.email, types),
        tools=CLASSIFY_TOOLS,
        tool_choice={"type": "any"},
        messages=[{
            "role": "user",
            "content": (
                f"From: {sender}\n"
                f"Subject: {subject}\n\n"
                f"{body[:8000] if body else '(empty body)'}"
            ),
        }],
    )

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if not tool_use:
        print("  ! Claude returned no tool call")
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["error"])
        return

    if tool_use.name == "discard":
        reason = (tool_use.input or {}).get("reason", "noise")
        print(f"  · discard ({reason})")
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["discarded"])
        return

    # extract_request
    args = tool_use.input or {}
    type_name = args.get("type", "")
    type_cfg = types_config.find(types, type_name)
    if not type_cfg:
        print(f"  ! Claude returned unknown type '{type_name}', discarding")
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["unknown-type"])
        return

    fields = args.get("fields", {}) or {}
    summary = args.get("summary", "")

    request_row = requests_store.append(
        thread_id=thread_id,
        type_name=type_name,
        summary=summary,
        fields=fields,
        source_message_id=message.message_id,
        source_sender=sender,
    )
    print(f"  ✓ extracted: {type_name}  (id {request_row['id']})  fields={list(fields.keys())}")

    # Email the user a clean review prompt — they reply approve/decline
    try:
        agentmail.inboxes.messages.reply(
            inbox.inbox_id, message.message_id,
            to=[USER_EMAIL],  # explicitly route to user, not back to original sender
            text=_format_review_email(request_row, fields, type_cfg),
        )
        print(f"  ✓ review email sent to {USER_EMAIL}")
    except Exception as e:
        print(f"  ! review send failed (falling back to send): {e}")
        # Fall back to send if reply doesn't accept overriding `to`
        agentmail.inboxes.messages.send(
            inbox.inbox_id,
            to=[USER_EMAIL],
            subject=f"[Approval needed] {summary}",
            text=_format_review_email(request_row, fields, type_cfg),
        )

    _mark_read(inbox.inbox_id, message.message_id, add_labels=[f"req-{type_name}", "pending"])


def _handle_decision_reply(message, pending: dict, body: str, types: list, inbox):
    """User replied on a request thread — parse decision, fire actions, ack."""
    decision = reply_parser.parse(body)
    kind = decision["decision"]

    if kind == "unknown":
        print(f"  ? could not parse decision from reply (first line): '{body.strip().splitlines()[0][:80] if body.strip() else ''}'")
        try:
            agentmail.inboxes.messages.reply(
                inbox.inbox_id, message.message_id,
                text=(
                    "I couldn't parse your reply. Please reply with one of:\n"
                    "  approve\n"
                    "  decline (or 'decline: <reason>')\n"
                    "  defer 7d\n"
                    "  edit: <changes>\n\n"
                    "— Approval inbox"
                ),
            )
        except Exception:
            pass
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["unparseable"])
        return

    type_cfg = types_config.find(types, pending["type"])
    if not type_cfg:
        print(f"  ! type {pending['type']} no longer configured, can't fire actions")
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["stale-type"])
        return

    decided_text = body.strip().splitlines()[0][:200] if body.strip() else ""
    new_status_map = {
        "approve": "approved",
        "decline": "declined",
        "defer": "deferred",
        "changes": "changes_requested",
    }
    new_status = new_status_map[kind]
    requests_store.update_status(pending["id"], new_status, decided_text)
    print(f"  ✓ decision: {kind}  (request {pending['id']})")

    # Fire side-effect actions (only on approve/decline; defer/changes just update status)
    confirmations: list[str] = []
    if kind in {"approve", "decline"}:
        decision_args = {}
        if kind == "decline":
            decision_args["reason"] = decision.get("reason", "")
        confirmations = actions_mod.fire(
            agentmail_client=agentmail, inbox=inbox,
            request_row=pending, type_config=type_cfg,
            decision="approve" if kind == "approve" else "decline",
            decision_args=decision_args,
        )
    elif kind == "defer":
        confirmations.append(f"deferred for {decision.get('days', 1)} day(s)")
    elif kind == "changes":
        ctext = decision.get("changes_text", "")
        confirmations.append(f"marked as changes-requested" + (f": '{ctext[:100]}'" if ctext else ""))

    try:
        agentmail.inboxes.messages.reply(
            inbox.inbox_id, message.message_id,
            text=_format_decision_ack(kind, pending, confirmations),
        )
    except Exception as e:
        print(f"  ! ack failed: {e}")

    _mark_read(inbox.inbox_id, message.message_id, add_labels=[f"decided-{new_status}"])


# --- main loop ----------------------------------------------------------------


def main():
    print(f"--- Approval Inbox  ·  {USER_NAME} ---")
    inbox = get_or_create_inbox()
    types = types_config.load()

    print(f"Inbox: {inbox.email}  (id: {inbox.inbox_id})")
    print(f"User:  {USER_EMAIL}")
    print(f"Configured types ({len(types)}): {', '.join(t.type for t in types) if types else '(none — edit approval_types.yaml)'}")
    print(f"Polling every {POLL_INTERVAL}s.\n")

    while True:
        try:
            # Reload types each iteration so config edits take effect live
            types = types_config.load()

            unread = agentmail.inboxes.messages.list(inbox.inbox_id, labels=["unread"])
            messages = unread.messages or []
            if messages:
                print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {len(messages)} unread")
                for m in messages:
                    try:
                        process_message(m, inbox, types)
                    except Exception as e:
                        print(f"  ! error on {m.message_id}: {e}")

        except Exception as e:
            print(f"! poll loop error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
