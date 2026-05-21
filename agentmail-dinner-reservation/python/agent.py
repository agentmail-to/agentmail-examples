"""
AgentMail Dinner Reservation Agent — emails restaurants on your behalf,
handles their replies, confirms your booking.

Flow:
    User → Agent → Restaurant → Agent → User
                              ↓
                    (alternative / decline / confirm)

Run:
    pip install -r requirements.txt
    cp .env.example .env   # then fill in your keys
    python agent.py
"""

import json
import os
import time
import uuid
from email.utils import parseaddr
from pathlib import Path

from agentmail import AgentMail
from agentmail.inboxes import CreateInboxRequest
from anthropic import Anthropic
from dotenv import load_dotenv

import reservations
from calendar_invite import build_ics, ics_attachment
from prompt import build_system_prompt

load_dotenv()

# --- config -------------------------------------------------------------------

AGENTMAIL_API_KEY = os.environ["AGENTMAIL_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
USER_NAME = os.getenv("USER_NAME", "the user")
USER_EMAIL = os.environ["USER_EMAIL"].lower()
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "15"))
INBOX_USERNAME = os.getenv("INBOX_USERNAME") or None

STATE_FILE = Path(".agent_state.json")

# --- clients ------------------------------------------------------------------

agentmail = AgentMail(api_key=AGENTMAIL_API_KEY)
claude = Anthropic(api_key=ANTHROPIC_API_KEY)


# --- Claude tools -------------------------------------------------------------

EMAIL_RESTAURANT_TOOL = {
    "name": "email_restaurant",
    "description": "Send the booking request to the restaurant. Use ONLY when you have all required details from the user.",
    "input_schema": {
        "type": "object",
        "required": ["restaurant_email", "restaurant_name", "date", "time", "party_size", "message"],
        "properties": {
            "restaurant_email": {"type": "string", "description": "The restaurant's reservations email."},
            "restaurant_name": {"type": "string"},
            "date": {"type": "string", "description": "ISO date or natural like 'Friday May 1 2026'."},
            "time": {"type": "string", "description": "e.g. '7:00 PM'."},
            "party_size": {"type": "integer"},
            "dietary": {"type": "string", "description": "Optional dietary restrictions / preferences."},
            "message": {"type": "string", "description": "The full email body to send the restaurant. Under 80 words, professional, includes all details, asks them to confirm by reply."},
        },
    },
}

ASK_USER_TOOL = {
    "name": "ask_user",
    "description": "Reply to the user's thread with ONE specific clarifying question.",
    "input_schema": {
        "type": "object",
        "required": ["question"],
        "properties": {"question": {"type": "string"}},
    },
}

CONFIRM_TO_USER_TOOL = {
    "name": "confirm_to_user",
    "description": (
        "Restaurant confirmed. Reply to the user's thread with structured "
        "confirmation, and attach a calendar invite (.ics)."
    ),
    "input_schema": {
        "type": "object",
        "required": ["restaurant_name", "date", "time", "party_size", "start_iso", "summary"],
        "properties": {
            "restaurant_name": {"type": "string"},
            "date": {"type": "string", "description": "Human-readable date (e.g. 'Friday May 1, 2026')."},
            "time": {"type": "string", "description": "Human-readable time (e.g. '7:00 PM PT')."},
            "start_iso": {
                "type": "string",
                "description": (
                    "ISO 8601 start datetime with timezone offset, e.g. "
                    "'2026-05-01T19:00:00-07:00'. Always include the offset. "
                    "Used to generate the .ics calendar invite."
                ),
            },
            "duration_minutes": {
                "type": "integer",
                "description": "Reservation duration. Default 90 for dinner.",
            },
            "party_size": {"type": "integer"},
            "restaurant_contact": {"type": "string", "description": "Name / role of the person who confirmed, if mentioned."},
            "summary": {"type": "string", "description": "1-2 sentence note about anything else the restaurant mentioned (dress code, menu, pre-payment, etc.)."},
        },
    },
}

FORWARD_ALTERNATIVE_TOOL = {
    "name": "forward_alternative_to_user",
    "description": "Restaurant offered a different date/time. Tell the user and ask if it works.",
    "input_schema": {
        "type": "object",
        "required": ["restaurant_name", "alternative_offered", "summary"],
        "properties": {
            "restaurant_name": {"type": "string"},
            "alternative_offered": {"type": "string", "description": "The new date/time/etc the restaurant offered."},
            "summary": {"type": "string", "description": "Brief context."},
        },
    },
}

TELL_USER_DECLINE_TOOL = {
    "name": "tell_user_decline",
    "description": "Restaurant declined or fully booked. Tell the user.",
    "input_schema": {
        "type": "object",
        "required": ["restaurant_name", "reason"],
        "properties": {
            "restaurant_name": {"type": "string"},
            "reason": {"type": "string"},
            "suggestion": {"type": "string", "description": "Optional next-step suggestion (try another time, suggest similar restaurants)."},
        },
    },
}

TOOLS = [
    EMAIL_RESTAURANT_TOOL,
    ASK_USER_TOOL,
    CONFIRM_TO_USER_TOOL,
    FORWARD_ALTERNATIVE_TOOL,
    TELL_USER_DECLINE_TOOL,
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
            display_name=f"{USER_NAME}'s reservation agent",
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


# --- tool handlers ------------------------------------------------------------


def handle_email_restaurant(args, message, inbox):
    rid = uuid.uuid4().hex[:8]
    print(f"  📧 emailing restaurant {args['restaurant_name']} ({args['restaurant_email']})")
    subject = f"Reservation Request — {args['date']} — Party of {args['party_size']}"
    sent = agentmail.inboxes.messages.send(
        inbox_id=inbox.inbox_id,
        to=[args["restaurant_email"]],
        subject=subject,
        text=args["message"],
    )

    # The send response gives us the message_id and thread_id of the new outbound thread
    restaurant_thread_id = getattr(sent, "thread_id", None) or getattr(sent, "message_id", None)
    reservations.upsert(
        rid,
        status="awaiting_restaurant",
        restaurant_email=args["restaurant_email"],
        restaurant_name=args["restaurant_name"],
        restaurant_thread_id=restaurant_thread_id,
        user_thread_id=message.thread_id,
        details={
            "date": args["date"],
            "time": args["time"],
            "party_size": args["party_size"],
            "dietary": args.get("dietary", ""),
        },
    )

    # Acknowledge the user
    ack = (
        f"Got it — emailing {args['restaurant_name']} now to request a table for "
        f"{args['party_size']} on {args['date']} at {args['time']}. "
        f"I'll forward their reply as soon as it lands."
    )
    agentmail.inboxes.messages.reply(
        inbox.inbox_id, message.message_id, text=ack
    )


def handle_ask_user(args, message, inbox):
    print(f"  ❓ asking user: {args['question'][:80]}")
    agentmail.inboxes.messages.reply(
        inbox.inbox_id, message.message_id, text=args["question"]
    )


def _reply_in_user_thread(reservation: dict, body: str, inbox, attachments=None) -> None:
    """Reply to the user in the original request thread, optionally with attachments."""
    user_thread_id = reservation.get("user_thread_id")
    if not user_thread_id:
        # Fallback: send a new email to USER_EMAIL
        agentmail.inboxes.messages.send(
            inbox_id=inbox.inbox_id,
            to=[USER_EMAIL],
            subject=f"Reservation update — {reservation.get('restaurant_name', '')}",
            text=body,
            attachments=attachments,
        )
        return

    # Find the latest message in the user thread to reply to
    thread = agentmail.inboxes.threads.get(inbox.inbox_id, user_thread_id)
    user_msgs = [
        m for m in (thread.messages or [])
        if _sender_email(m) == USER_EMAIL
    ]
    target = user_msgs[-1] if user_msgs else (thread.messages[-1] if thread.messages else None)
    if target:
        agentmail.inboxes.messages.reply(
            inbox.inbox_id, target.message_id, text=body, attachments=attachments,
        )
    else:
        agentmail.inboxes.messages.send(
            inbox_id=inbox.inbox_id,
            to=[USER_EMAIL],
            subject="Reservation update",
            text=body,
            attachments=attachments,
        )


def handle_confirm_to_user(args, message, inbox):
    rec = reservations.find_by_restaurant_thread(message.thread_id)
    if not rec:
        print("  ! no reservation matches this thread, falling back")
        rec = {"restaurant_name": args["restaurant_name"]}
    print(f"  ✅ confirming to user: {args['restaurant_name']} on {args['date']} at {args['time']}")

    contact = args.get("restaurant_contact", "").strip()
    contact_line = f"\nConfirmed by: {contact}" if contact else ""
    body = (
        f"CONFIRMED ✓\n\n"
        f"Restaurant: {args['restaurant_name']}\n"
        f"Date: {args['date']} at {args['time']}\n"
        f"Party: {args['party_size']} people"
        f"{contact_line}\n\n"
        f"{args['summary']}\n\n"
        f"📅 Calendar invite attached — open it to add to your calendar."
    )

    # Generate the .ics calendar invite. Both attendees (user + restaurant) get
    # listed so the invite shows up properly in Gmail / Outlook / Apple Mail.
    attachments = None
    try:
        attendees = [USER_EMAIL]
        if rec.get("restaurant_email"):
            attendees.append(rec["restaurant_email"])
        ics = build_ics(
            title=f"Dinner at {args['restaurant_name']} (party of {args['party_size']})",
            start_iso=args["start_iso"],
            duration_minutes=int(args.get("duration_minutes", 90)),
            organizer_email=inbox.email,
            attendees=attendees,
            description=args.get("summary", ""),
        )
        attachments = [ics_attachment(ics, filename=f"dinner-{args['restaurant_name'].lower().replace(' ', '-')}.ics")]
        print(f"  📅 calendar invite attached ({args['start_iso']}, {args.get('duration_minutes', 90)} min)")
    except Exception as e:
        print(f"  ! couldn't build calendar invite: {e}")

    _reply_in_user_thread(rec, body, inbox, attachments=attachments)
    if rec.get("id"):
        reservations.upsert(rec["id"], status="confirmed")


def handle_forward_alternative_to_user(args, message, inbox):
    rec = reservations.find_by_restaurant_thread(message.thread_id) or {}
    print(f"  ↪  alternative from {args['restaurant_name']}: {args['alternative_offered']}")
    body = (
        f"ALTERNATIVE OFFERED ↪\n\n"
        f"{args['restaurant_name']} can't do the original time. They suggested: "
        f"{args['alternative_offered']}\n\n"
        f"{args['summary']}\n\n"
        f"Reply with 'yes' to take it, or tell me what to do instead."
    )
    _reply_in_user_thread(rec, body, inbox)
    if rec.get("id"):
        reservations.upsert(rec["id"], status="alternative_offered",
                           alternative=args["alternative_offered"])


def handle_tell_user_decline(args, message, inbox):
    rec = reservations.find_by_restaurant_thread(message.thread_id) or {}
    print(f"  ✗ {args['restaurant_name']} declined: {args['reason']}")
    suggestion = args.get("suggestion", "").strip()
    body = (
        f"DECLINED ✗\n\n"
        f"{args['restaurant_name']}: {args['reason']}\n\n"
        f"{suggestion if suggestion else 'Want me to try another time or another restaurant? Just reply with the details.'}"
    )
    _reply_in_user_thread(rec, body, inbox)
    if rec.get("id"):
        reservations.upsert(rec["id"], status="declined")


TOOL_HANDLERS = {
    "email_restaurant": handle_email_restaurant,
    "ask_user": handle_ask_user,
    "confirm_to_user": handle_confirm_to_user,
    "forward_alternative_to_user": handle_forward_alternative_to_user,
    "tell_user_decline": handle_tell_user_decline,
}


# --- core processing ----------------------------------------------------------


def classify_sender(message) -> str:
    """Return 'user', 'restaurant', or 'unknown'.

    We check thread_id first so that any reply on an active restaurant thread
    is classified as a restaurant reply — even if it happens to come from
    USER_EMAIL (e.g., the user's mail was plus-addressed and the reply stripped
    the tag, or any other forwarding setup that collapses the sender). Replies
    on the user's original request thread fall through to the user check.
    """
    if reservations.find_by_restaurant_thread(message.thread_id):
        return "restaurant"
    if _sender_email(message) == USER_EMAIL:
        return "user"
    return "unknown"


def process_message(message, inbox):
    sender_kind = classify_sender(message)
    print(f"  → sender_kind={sender_kind}")

    if sender_kind == "unknown":
        print("  ! unknown sender, skipping")
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["unknown_sender"])
        return

    # Fetch the full thread for context
    thread = agentmail.inboxes.threads.get(inbox.inbox_id, message.thread_id)
    full_msgs = thread.messages or []
    if not full_msgs:
        _mark_read(inbox.inbox_id, message.message_id)
        return

    # Build a context payload for Claude based on the email source
    latest = full_msgs[-1]
    body = (getattr(latest, "extracted_text", None) or latest.text or "").strip()

    if sender_kind == "user":
        context_header = (
            f"[INBOUND USER REQUEST]\n"
            f"From: {latest.from_}\n"
            f"Subject: {latest.subject}\n\n"
        )
    else:
        rec = reservations.find_by_restaurant_thread(message.thread_id) or {}
        context_header = (
            f"[RESTAURANT REPLY]\n"
            f"Restaurant: {rec.get('restaurant_name', '?')}\n"
            f"Original request: {rec.get('details', {})}\n"
            f"From: {latest.from_}\n"
            f"Subject: {latest.subject}\n\n"
        )

    user_payload = context_header + (body[:4000] or "(empty body)")

    print(f"  → asking Claude (model={MODEL})")
    response = claude.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=build_system_prompt(inbox_email=inbox.email),
        tools=TOOLS,
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": user_payload}],
    )

    handled = False
    for block in response.content:
        if block.type == "tool_use" and block.name in TOOL_HANDLERS:
            try:
                TOOL_HANDLERS[block.name](block.input, message, inbox)
                handled = True
                _mark_read(inbox.inbox_id, message.message_id,
                          add_labels=[sender_kind, block.name])
            except Exception as e:
                print(f"  ! tool handler {block.name} failed: {e}")

    if not handled:
        print("  ! Claude did not call any tool")
        _mark_read(inbox.inbox_id, message.message_id)


# --- main loop ----------------------------------------------------------------


def main():
    inbox = get_or_create_inbox()
    print(f"\n📬 Reservation agent live at: {inbox.email}")
    print(f"   Email reservation requests there from {USER_EMAIL}.")
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
                    continue  # skip our own outgoing mail
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
