"""
AgentMail GTM Agent — personalized multi-touch outreach + reply handling + handoffs.

Workflow:
  1. Read prospects from prospects.csv.
  2. For each queued prospect, send a personalized first-touch email.
  3. After FOLLOWUP_AFTER_HOURS with no reply, send one follow-up. Then stop.
  4. Watch for replies, classify (interested / not_interested / ooo / question),
     forward interested leads to SALES_EMAIL with handoff context.
  5. Append every action to gtm_log.csv.

Run:
    pip install -r requirements.txt
    cp .env.example .env
    cp prospects.example.csv prospects.csv  # edit this with your real prospects
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

import prospects
from prompt import build_classifier_prompt, build_writer_prompt

load_dotenv()

# --- config -------------------------------------------------------------------

AGENTMAIL_API_KEY = os.environ["AGENTMAIL_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SENDER_NAME = os.getenv("SENDER_NAME", "Sender")
SENDER_COMPANY = os.getenv("SENDER_COMPANY", "Company")
SALES_EMAIL = os.environ["SALES_EMAIL"]
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
FOLLOWUP_AFTER_HOURS = int(os.getenv("FOLLOWUP_AFTER_HOURS", "96"))  # 4 days default
INBOX_USERNAME = os.getenv("INBOX_USERNAME") or None

STATE_FILE = Path(".agent_state.json")

# --- clients ------------------------------------------------------------------

agentmail = AgentMail(api_key=AGENTMAIL_API_KEY)
claude = Anthropic(api_key=ANTHROPIC_API_KEY)


# --- Claude tools (reply classification) --------------------------------------

MARK_INTERESTED_TOOL = {
    "name": "mark_interested",
    "description": (
        "Reply shows positive interest. Sends an immediate warm acknowledgment "
        "back to the prospect in the same thread (keeps them engaged while the "
        "sales team picks up), then forwards the original reply to the sales "
        "team with handoff context."
    ),
    "input_schema": {
        "type": "object",
        "required": ["prospect_acknowledgment", "summary", "handoff_note"],
        "properties": {
            "prospect_acknowledgment": {
                "type": "string",
                "description": (
                    "2-3 sentence warm reply to send the prospect IMMEDIATELY in "
                    "the same thread. Acknowledges their interest specifically "
                    "(reference what they said, not generically) and sets a soft "
                    "expectation ('our team will follow up shortly'). "
                    "CRITICAL: NEVER invent a specific salesperson name — refer "
                    "to 'our team' or 'our sales team' generically. You don't "
                    "know who's on the sales rotation, so naming someone risks "
                    "hallucinating a person who doesn't exist. "
                    "Also DO NOT promise specific times, prices, or anything the "
                    "sales team should own. Keep the agent's voice consistent "
                    "with the original cold email — direct, no fluff."
                ),
            },
            "summary": {"type": "string", "description": "1-2 sentence summary of the prospect's signal."},
            "handoff_note": {"type": "string", "description": "Cover note for the sales team — what to know + a suggested next step."},
        },
    },
}

MARK_NOT_INTERESTED_TOOL = {
    "name": "mark_not_interested",
    "description": "Reply is a decline. Stop touching this prospect. We do NOT reply to declines.",
    "input_schema": {
        "type": "object",
        "required": ["reason"],
        "properties": {"reason": {"type": "string"}},
    },
}

MARK_OOO_TOOL = {
    "name": "mark_ooo",
    "description": "Reply is an out-of-office / vacation auto-reply. Pause; don't follow up until they're back.",
    "input_schema": {
        "type": "object",
        "required": ["return_date_or_note"],
        "properties": {"return_date_or_note": {"type": "string"}},
    },
}

MARK_QUESTION_TOOL = {
    "name": "mark_question",
    "description": "Prospect is asking a clarifying question without taking a clear side. Provide a suggested response we'll send in-thread.",
    "input_schema": {
        "type": "object",
        "required": ["suggested_response"],
        "properties": {
            "suggested_response": {"type": "string", "description": "2-3 sentence reply to send in the same thread."},
        },
    },
}

CLASSIFIER_TOOLS = [
    MARK_INTERESTED_TOOL,
    MARK_NOT_INTERESTED_TOOL,
    MARK_OOO_TOOL,
    MARK_QUESTION_TOOL,
]


# --- helpers ------------------------------------------------------------------


def _sender_email(message) -> str:
    sender = getattr(message, "from_", None) or getattr(message, "from", None) or ""
    _, email = parseaddr(str(sender))
    return email.lower()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


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
            display_name=f"{SENDER_NAME} - {SENDER_COMPANY}",
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


# --- outreach (writing + sending) ---------------------------------------------


def write_email_body(prospect: dict, touch: str = "first") -> str:
    """Use Claude (no tools) to compose a personalized email body."""
    user_payload = (
        f"Touch: {touch}\n\n"
        f"Prospect:\n"
        f"  Name: {prospect['name']}\n"
        f"  Role: {prospect['role']}\n"
        f"  Company: {prospect['company']}\n"
        f"  Hook (specific signal to lead with): {prospect['hook']}\n"
    )
    response = claude.messages.create(
        model=MODEL,
        max_tokens=400,
        system=build_writer_prompt(),
        messages=[{"role": "user", "content": user_payload}],
    )
    return next(
        (b.text for b in response.content if b.type == "text"),
        ""
    ).strip()


def send_first_touch(prospect: dict, inbox) -> None:
    print(f"  ✉  first touch → {prospect['email']} ({prospect['name']}, {prospect['company']})")
    body = write_email_body(prospect, touch="first")
    if not body:
        print(f"    ! empty body, skipping")
        return
    subject_line = _subject_from_hook(prospect["hook"], prospect["company"])

    sent = agentmail.inboxes.messages.send(
        inbox_id=inbox.inbox_id,
        to=[prospect["email"]],
        subject=subject_line,
        text=body,
    )
    thread_id = getattr(sent, "thread_id", None) or getattr(sent, "message_id", "")
    prospects.update_prospect(
        prospect["email"],
        status="first_touch_sent",
        first_touch_at=_now_iso(),
        thread_id=thread_id,
    )
    prospects.log_action(
        action="first_touch", prospect_email=prospect["email"],
        thread_id=thread_id, note=body[:200],
    )


def send_followup(prospect: dict, inbox) -> None:
    print(f"  ↪  follow-up → {prospect['email']}")
    body = write_email_body(prospect, touch="follow-up")
    if not body:
        return

    # Reply in the existing thread
    if prospect["thread_id"]:
        try:
            thread = agentmail.inboxes.threads.get(inbox.inbox_id, prospect["thread_id"])
            # Find the most recent outbound message in the thread (ours) and reply to it
            our_msgs = [m for m in (thread.messages or []) if _sender_email(m) == inbox.email.lower()]
            target = our_msgs[-1] if our_msgs else (thread.messages[-1] if thread.messages else None)
            if target:
                agentmail.inboxes.messages.reply(
                    inbox.inbox_id, target.message_id, text=body
                )
        except Exception as e:
            print(f"    ! reply failed, falling back to new send: {e}")
            agentmail.inboxes.messages.send(
                inbox_id=inbox.inbox_id, to=[prospect["email"]],
                subject=f"Re: {_subject_from_hook(prospect['hook'], prospect['company'])}",
                text=body,
            )

    prospects.update_prospect(
        prospect["email"],
        status="followed_up",
        followup_at=_now_iso(),
    )
    prospects.log_action(
        action="follow_up", prospect_email=prospect["email"],
        thread_id=prospect["thread_id"], note=body[:200],
    )


def _subject_from_hook(hook: str, company: str) -> str:
    """Generate a short subject line from the hook."""
    hook = (hook or "").strip().rstrip(".")
    if not hook:
        return f"Quick question about {company}" if company else "Quick question"
    # Truncate aggressively
    return hook[:60] if len(hook) <= 60 else hook[:57] + "…"


# --- reply classification + handoff -------------------------------------------


def handle_mark_interested(args, message, inbox, prospect):
    summary = args.get("summary", "").strip()
    note = args.get("handoff_note", "").strip()
    ack = args.get("prospect_acknowledgment", "").strip()
    print(f"  🎯 INTERESTED: {summary}")

    # 1. Send warm acknowledgment to prospect FIRST (in the same thread). Keeps
    #    the conversation alive while sales picks up. Without this, the prospect
    #    sits in silence between their reply and the sales-team's response —
    #    a real risk for losing a hot lead.
    if ack:
        try:
            agentmail.inboxes.messages.reply(
                inbox.inbox_id, message.message_id, text=ack
            )
            print(f"  💬 warm ack sent to prospect ({len(ack)} chars)")
        except Exception as e:
            print(f"    ! warm ack failed: {e}")

    # 2. Forward original reply to the sales team with the handoff note
    try:
        agentmail.inboxes.messages.forward(
            inbox.inbox_id, message.message_id,
            to=[SALES_EMAIL],
            text=(
                f"[INTERESTED LEAD]\n\n"
                f"Prospect: {prospect['name']} <{prospect['email']}> "
                f"({prospect['role']} at {prospect['company']})\n\n"
                f"Summary: {summary}\n\n"
                f"Suggested next step: {note}\n\n"
                f"---\n"
                f"Note: I've already sent a warm acknowledgment to the prospect "
                f"in-thread — they're expecting your follow-up shortly. The "
                f"original reply is quoted below."
            ),
        )
    except Exception as e:
        print(f"    ! handoff forward failed: {e}")

    prospects.update_prospect(
        prospect["email"],
        status="handed_off",
        replied_at=_now_iso(),
        classification="interested",
    )
    prospects.log_action(
        action="handed_off", prospect_email=prospect["email"],
        classification="interested", thread_id=message.thread_id, note=summary,
    )


def handle_mark_not_interested(args, message, inbox, prospect):
    reason = args.get("reason", "").strip()
    print(f"  ✗ NOT INTERESTED: {reason}")
    prospects.update_prospect(
        prospect["email"],
        status="closed_lost",
        replied_at=_now_iso(),
        classification="not_interested",
    )
    prospects.log_action(
        action="closed_lost", prospect_email=prospect["email"],
        classification="not_interested", thread_id=message.thread_id, note=reason,
    )


def handle_mark_ooo(args, message, inbox, prospect):
    note = args.get("return_date_or_note", "").strip()
    print(f"  🏖  OOO: {note}")
    prospects.update_prospect(
        prospect["email"],
        status="paused_ooo",
        classification="ooo",
    )
    prospects.log_action(
        action="paused_ooo", prospect_email=prospect["email"],
        classification="ooo", thread_id=message.thread_id, note=note,
    )


def handle_mark_question(args, message, inbox, prospect):
    suggested = args.get("suggested_response", "").strip()
    print(f"  ❓ QUESTION: replying with {len(suggested)} chars")
    if not suggested:
        return
    agentmail.inboxes.messages.reply(
        inbox.inbox_id, message.message_id, text=suggested
    )
    prospects.update_prospect(
        prospect["email"],
        status="q_and_a",
        replied_at=_now_iso(),
        classification="question",
    )
    prospects.log_action(
        action="answered_question", prospect_email=prospect["email"],
        classification="question", thread_id=message.thread_id, note=suggested[:200],
    )


CLASSIFIER_HANDLERS = {
    "mark_interested": handle_mark_interested,
    "mark_not_interested": handle_mark_not_interested,
    "mark_ooo": handle_mark_ooo,
    "mark_question": handle_mark_question,
}


# --- core processing ----------------------------------------------------------


def process_reply(message, inbox):
    prospect = prospects.find_by_thread(message.thread_id)
    if not prospect:
        print("  ! reply on a thread with no tracked prospect, skipping")
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["unknown"])
        return

    print(f"  → reply from {prospect['email']} ({prospect['name']}, {prospect['company']})")
    thread = agentmail.inboxes.threads.get(inbox.inbox_id, message.thread_id)
    latest = (thread.messages or [])[-1]
    body = (getattr(latest, "extracted_text", None) or latest.text or "").strip()

    user_payload = (
        f"Original outreach to {prospect['name']} ({prospect['role']} at {prospect['company']}).\n"
        f"Hook used: {prospect['hook']}\n\n"
        f"--- Their reply ---\n{body[:4000]}"
    )

    print(f"  → asking Claude to classify (model={MODEL})")
    response = claude.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=build_classifier_prompt(),
        tools=CLASSIFIER_TOOLS,
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": user_payload}],
    )

    handled = False
    for block in response.content:
        if block.type == "tool_use" and block.name in CLASSIFIER_HANDLERS:
            try:
                CLASSIFIER_HANDLERS[block.name](block.input, message, inbox, prospect)
                handled = True
                _mark_read(inbox.inbox_id, message.message_id,
                          add_labels=[block.name.replace("mark_", "")])
            except Exception as e:
                print(f"  ! handler {block.name} failed: {e}")

    if not handled:
        print("  ! Claude did not call any tool")
        _mark_read(inbox.inbox_id, message.message_id)


# --- main loop ----------------------------------------------------------------


def main():
    inbox = get_or_create_inbox()
    print(f"\n📬 GTM agent live at: {inbox.email}")
    print(f"   Sender: {SENDER_NAME}, {SENDER_COMPANY}")
    print(f"   Sales team handoff: {SALES_EMAIL}")
    print(f"   Follow-up cadence: {FOLLOWUP_AFTER_HOURS}h after first touch")
    print(f"   Polling every {POLL_INTERVAL}s. Ctrl-C to stop.\n")

    seen: set[str] = set()

    while True:
        try:
            # 1) Send first-touch to any queued prospects
            for p in prospects.queued_prospects():
                try:
                    send_first_touch(p, inbox)
                except Exception as e:
                    print(f"  ! first-touch failed for {p['email']}: {e}")

            # 2) Send follow-ups for stale prospects
            for p in prospects.followups_due(FOLLOWUP_AFTER_HOURS):
                try:
                    send_followup(p, inbox)
                except Exception as e:
                    print(f"  ! follow-up failed for {p['email']}: {e}")

            # 3) Process replies
            resp = agentmail.inboxes.messages.list(inbox.inbox_id, labels=["unread"])
            new_msgs = [m for m in (resp.messages or []) if m.message_id not in seen]
            for m in new_msgs:
                seen.add(m.message_id)
                if _sender_email(m) == inbox.email.lower():
                    continue
                print(f"\n📩 from {_sender_email(m)}: {(m.subject or '(no subject)')[:60]}")
                try:
                    process_reply(m, inbox)
                except Exception as e:
                    print(f"  ! error processing reply: {e}")

        except Exception as e:
            print(f"poll error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
