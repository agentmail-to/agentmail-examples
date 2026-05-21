"""
AgentMail Negotiation Agent — multi-party email negotiation.

Workflow:
  1. Read deal.json (item, must-haves, ideal/max price, counterparty list).
  2. Send opening outreach to each counterparty in parallel.
  3. For each reply, Claude calls one of:
       - record_offer(price, terms, meets_must_haves, notes)
       - mark_declined(reason)
       - answer_question(reply_text)
  4. When all counterparties have responded (or timed out), Claude composes
     a round summary email to the buyer with a comparison table + recommended
     next move. Buyer replies with strategy ("counter A at $34k, walk B").
  5. Agent reads the buyer's strategy reply, dispatches counter emails or
     walk-aways accordingly. Loop until buyer says stop or ideal_price hit.

HARD RULES (enforced via prompts):
  - Never reveal buyer's name/location/budget to counterparties.
  - Never auto-accept. Buyer always confirms via the round-summary thread.
  - Escalate (with `target_hit_alert`) when any offer crosses ideal_price.

Run:
    pip install -r requirements.txt
    cp deal.example.json deal.json   # then edit your deal
    cp .env.example .env             # then add keys + BUYER_EMAIL
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

import deal
from prompt import (
    build_reply_classifier_prompt,
    build_round_summary_prompt,
    build_writer_prompt,
)

load_dotenv()

# --- config -------------------------------------------------------------------

AGENTMAIL_API_KEY = os.environ["AGENTMAIL_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
BUYER_EMAIL = os.environ["BUYER_EMAIL"].lower()
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
INBOX_USERNAME = os.getenv("INBOX_USERNAME") or None

STATE_FILE = Path(".agent_state.json")

# --- clients ------------------------------------------------------------------

agentmail = AgentMail(api_key=AGENTMAIL_API_KEY)
claude = Anthropic(api_key=ANTHROPIC_API_KEY)


# --- per-reply tools (counterparty replies) -----------------------------------

RECORD_OFFER_TOOL = {
    "name": "record_offer",
    "description": "Counterparty quoted a price/terms. Capture the structured fields.",
    "input_schema": {
        "type": "object",
        "required": ["price", "currency", "terms_summary", "meets_must_haves", "notes"],
        "properties": {
            "price": {"type": "number", "description": "The total price they quoted (OTD / all-in if mentioned, otherwise headline)."},
            "currency": {"type": "string"},
            "terms_summary": {"type": "string", "description": "1-2 sentences summarizing the terms (validity, fees, financing, etc.)"},
            "meets_must_haves": {"type": "boolean", "description": "True ONLY if every must-have is explicitly satisfied. False if any are unstated or missing."},
            "notes": {"type": "string", "description": "Anything else relevant — alternate price tiers, conditions, gaps in must-haves."},
        },
    },
}

MARK_DECLINED_TOOL = {
    "name": "mark_declined",
    "description": "Counterparty passed / can't fulfill. Stop pursuing them.",
    "input_schema": {
        "type": "object",
        "required": ["reason"],
        "properties": {"reason": {"type": "string"}},
    },
}

ANSWER_QUESTION_TOOL = {
    "name": "answer_question",
    "description": "Counterparty asked a clarifying question they need answered before quoting. Provide a short reply (under 60 words) with JUST the info needed — no buyer name/location, no other counterparties' offers.",
    "input_schema": {
        "type": "object",
        "required": ["reply_text"],
        "properties": {"reply_text": {"type": "string"}},
    },
}

REPLY_TOOLS = [RECORD_OFFER_TOOL, MARK_DECLINED_TOOL, ANSWER_QUESTION_TOOL]

# --- round summary tool -------------------------------------------------------

SEND_ROUND_SUMMARY_TOOL = {
    "name": "send_round_summary",
    "description": "Compose the round summary email to the buyer with comparison table + recommendation.",
    "input_schema": {
        "type": "object",
        "required": ["comparison_table", "recommended_action", "target_hit_alert", "report_body"],
        "properties": {
            "comparison_table": {"type": "string", "description": "Plain-text table of each counterparty's current state."},
            "recommended_action": {"type": "string", "description": "Concise next-move recommendation."},
            "target_hit_alert": {"type": "boolean", "description": "True if any counterparty crossed ideal_price (escalation flag)."},
            "report_body": {"type": "string", "description": "Full email body to send the buyer. Already includes greeting + comparison + recommendation + CTA."},
        },
    },
}

# --- buyer-reply (strategy) tools ---------------------------------------------

NEXT_ROUND_TOOL = {
    "name": "next_round",
    "description": "Buyer chose to counter one or more counterparties. Send each counter email and update statuses.",
    "input_schema": {
        "type": "object",
        "required": ["counters"],
        "properties": {
            "counters": {
                "type": "array",
                "description": "Ordered list of counter actions.",
                "items": {
                    "type": "object",
                    "required": ["counterparty_email", "anchor_price", "currency", "context_for_writer"],
                    "properties": {
                        "counterparty_email": {"type": "string"},
                        "anchor_price": {"type": "number", "description": "Price to anchor the counter at."},
                        "currency": {"type": "string"},
                        "context_for_writer": {"type": "string", "description": "Free-text context for the email writer (e.g. 'cite that Dealer X offered $33k', 'remind them about trade-in', 'final offer before walking')."},
                    },
                },
            },
        },
    },
}

WALK_AWAY_TOOL = {
    "name": "walk_away_from",
    "description": "Buyer wants to drop one or more counterparties out of the negotiation. Sends a polite close-out email.",
    "input_schema": {
        "type": "object",
        "required": ["counterparty_emails"],
        "properties": {
            "counterparty_emails": {"type": "array", "items": {"type": "string"}},
        },
    },
}

ESCALATE_FOR_HUMAN_TOOL = {
    "name": "escalate_for_human",
    "description": "Buyer wants to ACCEPT an offer. Per the rules, the agent NEVER auto-accepts — instead this confirms the escalation back to the buyer ('confirmed, the deal is in your hands now').",
    "input_schema": {
        "type": "object",
        "required": ["counterparty_email", "summary"],
        "properties": {
            "counterparty_email": {"type": "string"},
            "summary": {"type": "string"},
        },
    },
}

BUYER_STRATEGY_TOOLS = [NEXT_ROUND_TOOL, WALK_AWAY_TOOL, ESCALATE_FOR_HUMAN_TOOL]


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_or_create_inbox():
    state = load_state()
    if state.get("inbox_id"):
        try:
            return agentmail.inboxes.get(state["inbox_id"])
        except Exception as e:
            print(f"(stale state, creating new inbox: {e})")

    # AgentMail rejects punctuation like commas/parens in display_name. Strip
    # everything but letters/numbers/spaces/hyphens and trim length.
    import re
    deal_state = deal.load()
    raw_label = deal_state.get("what", "deal")
    label = re.sub(r"[^A-Za-z0-9 \-]+", "", raw_label).strip()[:40] or "deal"
    inbox = agentmail.inboxes.create(
        request=CreateInboxRequest(
            username=INBOX_USERNAME,
            display_name=f"Buyer's negotiator - {label}",
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


# --- writer (Claude composes outreach / counter) ------------------------------


def write_outreach_body(counterparty: dict, kind: str, extra_context: str = "") -> str:
    """kind: 'opening' | 'counter' | 'walk_away'"""
    deal_state = deal.load()
    user_payload = (
        f"Email kind: {kind}\n\n"
        f"Counterparty: {counterparty.get('name', '?')} <{counterparty.get('email', '')}>\n"
        f"Counterparty's previous offer (if any): "
        f"{json.dumps(counterparty.get('current_offer', {}), indent=2) if counterparty.get('current_offer') else 'none'}\n\n"
        f"Extra context for this email: {extra_context or '(none)'}\n\n"
        f"Compose the email body now."
    )
    response = claude.messages.create(
        model=MODEL, max_tokens=400,
        system=build_writer_prompt(),
        messages=[{"role": "user", "content": user_payload}],
    )
    return next((b.text for b in response.content if b.type == "text"), "").strip()


def send_opening(counterparty: dict, inbox) -> None:
    print(f"  ✉  opening → {counterparty['email']} ({counterparty.get('name', '?')})")
    body = write_outreach_body(counterparty, kind="opening")
    if not body:
        print("    ! empty body, skipping")
        return
    deal_state = deal.load()
    subject = f"Inquiry — {deal_state.get('what', 'item')[:60]}"
    sent = agentmail.inboxes.messages.send(
        inbox_id=inbox.inbox_id,
        to=[counterparty["email"]],
        subject=subject,
        text=body,
    )
    thread_id = getattr(sent, "thread_id", None) or getattr(sent, "message_id", "")
    deal.update_counterparty(
        counterparty["email"],
        status="contacted",
        thread_id=thread_id,
        contacted_at=_now_iso(),
    )


def send_counter(counterparty_email: str, anchor_price: float, currency: str,
                 extra_context: str, inbox) -> None:
    cp = deal.get_counterparty_by_email(counterparty_email)
    if not cp:
        print(f"  ! no counterparty {counterparty_email}, skipping counter")
        return
    print(f"  ↪  counter → {counterparty_email} at {anchor_price:.0f} {currency}")
    extra = f"Anchor at {anchor_price} {currency}. {extra_context}".strip()
    body = write_outreach_body(cp, kind="counter", extra_context=extra)
    if not body or not cp.get("thread_id"):
        return
    try:
        thread = agentmail.inboxes.threads.get(inbox.inbox_id, cp["thread_id"])
        # Reply to the most recent message in the thread
        target = thread.messages[-1] if thread.messages else None
        if target:
            agentmail.inboxes.messages.reply(
                inbox.inbox_id, target.message_id, text=body
            )
        deal.update_counterparty(
            counterparty_email,
            status="countered",
            last_counter_at=_now_iso(),
            last_anchor=anchor_price,
        )
    except Exception as e:
        print(f"    ! counter send failed: {e}")


def send_walk_away(counterparty_email: str, inbox) -> None:
    cp = deal.get_counterparty_by_email(counterparty_email)
    if not cp or not cp.get("thread_id"):
        return
    print(f"  ✗ walking away from {counterparty_email}")
    body = write_outreach_body(cp, kind="walk_away",
        extra_context="Polite close-out: we're going with another option, thank them for their time.")
    if not body:
        return
    try:
        thread = agentmail.inboxes.threads.get(inbox.inbox_id, cp["thread_id"])
        target = thread.messages[-1] if thread.messages else None
        if target:
            agentmail.inboxes.messages.reply(
                inbox.inbox_id, target.message_id, text=body
            )
        deal.update_counterparty(counterparty_email, status="walked")
    except Exception as e:
        print(f"    ! walk-away send failed: {e}")


# --- reply classification (counterparty side) ---------------------------------


def handle_record_offer(args, message, inbox, counterparty):
    print(f"  💰 offer from {counterparty['email']}: {args['price']:.0f} {args['currency']} "
          f"(meets_must_haves={args['meets_must_haves']})")
    deal.update_counterparty(
        counterparty["email"],
        status="offered",
        current_offer={
            "price": args["price"],
            "currency": args["currency"],
            "terms_summary": args.get("terms_summary", ""),
            "meets_must_haves": args.get("meets_must_haves", False),
            "notes": args.get("notes", ""),
            "received_at": _now_iso(),
        },
    )


def handle_mark_declined(args, message, inbox, counterparty):
    print(f"  ✗ declined: {counterparty['email']} — {args.get('reason', '')}")
    deal.update_counterparty(counterparty["email"], status="declined",
                            decline_reason=args.get("reason", ""))


def handle_answer_question(args, message, inbox, counterparty):
    reply = args.get("reply_text", "").strip()
    print(f"  ❓ answering question from {counterparty['email']} ({len(reply)} chars)")
    if reply:
        agentmail.inboxes.messages.reply(
            inbox.inbox_id, message.message_id, text=reply
        )


REPLY_HANDLERS = {
    "record_offer": handle_record_offer,
    "mark_declined": handle_mark_declined,
    "answer_question": handle_answer_question,
}


# --- buyer-reply (strategy) handlers ------------------------------------------


def handle_next_round(args, message, inbox):
    counters = args.get("counters", []) or []
    print(f"  → buyer chose to counter {len(counters)} counterparty(ies)")
    for c in counters:
        send_counter(
            counterparty_email=c["counterparty_email"],
            anchor_price=c["anchor_price"],
            currency=c.get("currency", "USD"),
            extra_context=c.get("context_for_writer", ""),
            inbox=inbox,
        )


def handle_walk_away(args, message, inbox):
    emails = args.get("counterparty_emails", []) or []
    print(f"  → buyer chose to walk from {len(emails)} counterparty(ies)")
    for em in emails:
        send_walk_away(em, inbox)


def handle_escalate_for_human(args, message, inbox):
    cp_email = args.get("counterparty_email", "")
    summary = args.get("summary", "")
    print(f"  🤝 buyer wants to ACCEPT {cp_email}: {summary}")
    # Per rules: agent does NOT close. We acknowledge to the buyer that the
    # deal is in their hands now.
    body = (
        f"Acknowledged — handing the close to you.\n\n"
        f"You'll need to reach out to {cp_email} directly to finalize. The "
        f"agent will not auto-accept on your behalf (this is a hard rule). "
        f"All current threads remain open until you tell me to walk away from them.\n\n"
        f"Summary: {summary}"
    )
    agentmail.inboxes.messages.reply(
        inbox.inbox_id, message.message_id, text=body
    )
    deal_state = deal.load()
    deal_state.setdefault("buyer_accept_intent", []).append({
        "counterparty_email": cp_email, "summary": summary, "at": _now_iso(),
    })
    deal.save(deal_state)


BUYER_STRATEGY_HANDLERS = {
    "next_round": handle_next_round,
    "walk_away_from": handle_walk_away,
    "escalate_for_human": handle_escalate_for_human,
}


# --- core processing ----------------------------------------------------------


def process_counterparty_reply(message, inbox, counterparty):
    print(f"  → counterparty reply from {counterparty['email']}")
    thread = agentmail.inboxes.threads.get(inbox.inbox_id, message.thread_id)
    latest = (thread.messages or [])[-1]
    body = (getattr(latest, "extracted_text", None) or latest.text or "").strip()

    user_payload = (
        f"Counterparty: {counterparty.get('name', '?')} <{counterparty['email']}>\n"
        f"Their previous offer (if any): {json.dumps(counterparty.get('current_offer', {}))}\n\n"
        f"--- Their reply ---\n{body[:4000]}"
    )

    response = claude.messages.create(
        model=MODEL, max_tokens=1024,
        system=build_reply_classifier_prompt(),
        tools=REPLY_TOOLS, tool_choice={"type": "any"},
        messages=[{"role": "user", "content": user_payload}],
    )

    handled = False
    for block in response.content:
        if block.type == "tool_use" and block.name in REPLY_HANDLERS:
            try:
                REPLY_HANDLERS[block.name](block.input, message, inbox, counterparty)
                handled = True
                _mark_read(inbox.inbox_id, message.message_id,
                          add_labels=["counterparty", block.name])
            except Exception as e:
                print(f"  ! handler {block.name} failed: {e}")
    if not handled:
        _mark_read(inbox.inbox_id, message.message_id)


def process_buyer_reply(message, inbox):
    print(f"  → buyer reply (strategy)")
    thread = agentmail.inboxes.threads.get(inbox.inbox_id, message.thread_id)
    latest = (thread.messages or [])[-1]
    body = (getattr(latest, "extracted_text", None) or latest.text or "").strip()

    deal_state = deal.load()
    snapshot = json.dumps(
        [{"email": cp.get("email"), "name": cp.get("name"),
          "status": cp.get("status"), "current_offer": cp.get("current_offer")}
         for cp in deal_state.get("counterparties", [])],
        indent=2,
    )

    system = (
        "You translate the buyer's strategy reply into structured tool calls. "
        "The buyer is responding to your last round-summary. They might say "
        "things like 'counter A with $34k, walk B' or 'accept C's offer' or "
        "'wait for D to reply first'.\n\n"
        "Available tools:\n"
        "- next_round(counters[]) — send counter offer(s) to one or more counterparties\n"
        "- walk_away_from(counterparty_emails[]) — close out one or more counterparties\n"
        "- escalate_for_human(counterparty_email, summary) — buyer wants to ACCEPT; we hand it back to them (we never auto-accept)\n\n"
        "If the buyer says 'wait' or 'hold' or 'let me think', call no tools.\n"
        "Always use exact counterparty emails from the deal state."
    )

    user_payload = (
        f"Current deal state:\n{snapshot}\n\n"
        f"--- Buyer's reply ---\n{body[:4000]}"
    )

    response = claude.messages.create(
        model=MODEL, max_tokens=2048,
        system=system,
        tools=BUYER_STRATEGY_TOOLS, tool_choice={"type": "auto"},
        messages=[{"role": "user", "content": user_payload}],
    )

    handled = False
    for block in response.content:
        if block.type == "tool_use" and block.name in BUYER_STRATEGY_HANDLERS:
            try:
                BUYER_STRATEGY_HANDLERS[block.name](block.input, message, inbox)
                handled = True
                _mark_read(inbox.inbox_id, message.message_id,
                          add_labels=["buyer", block.name])
            except Exception as e:
                print(f"  ! buyer-handler {block.name} failed: {e}")
    if not handled:
        # Buyer might be just chatting — acknowledge and idle
        print("  → no actionable strategy in buyer's reply, idling")
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["buyer", "idle"])


# --- round summary ------------------------------------------------------------


def maybe_send_round_summary(inbox):
    """When all counterparties have responded (offered/declined/walked), send
    the round-summary email to the buyer."""
    state = load_state()
    if state.get("round_summary_sent_for_round", 0) >= state.get("current_round", 1):
        return  # already sent for this round

    deal_state = deal.load()
    cps = deal_state.get("counterparties", [])
    if not cps:
        return
    if not deal.all_replied(deal_state):
        return  # waiting on more replies

    print(f"\n📊 Composing round {state.get('current_round', 1)} summary…")

    snapshot = [
        {
            "email": cp["email"], "name": cp.get("name", ""),
            "status": cp.get("status", ""),
            "current_offer": cp.get("current_offer"),
        }
        for cp in cps
    ]
    user_payload = (
        f"Round {state.get('current_round', 1)} state:\n"
        f"{json.dumps(snapshot, indent=2)}\n\n"
        f"Compose the round summary now."
    )

    response = claude.messages.create(
        model=MODEL, max_tokens=2048,
        system=build_round_summary_prompt(),
        tools=[SEND_ROUND_SUMMARY_TOOL], tool_choice={"type": "any"},
        messages=[{"role": "user", "content": user_payload}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "send_round_summary":
            args = block.input
            subject_prefix = "[TARGET HIT] " if args.get("target_hit_alert") else ""
            subject = (
                f"{subject_prefix}Negotiation update — round "
                f"{state.get('current_round', 1)} summary"
            )

            # Reply in the buyer's existing thread if we have one
            buyer_thread_id = state.get("buyer_thread_id")
            try:
                if buyer_thread_id:
                    thread = agentmail.inboxes.threads.get(inbox.inbox_id, buyer_thread_id)
                    buyer_msgs = [
                        m for m in (thread.messages or [])
                        if _sender_email(m) == BUYER_EMAIL
                    ]
                    target = buyer_msgs[-1] if buyer_msgs else None
                    if target:
                        agentmail.inboxes.messages.reply(
                            inbox.inbox_id, target.message_id, text=args["report_body"]
                        )
                    else:
                        agentmail.inboxes.messages.send(
                            inbox_id=inbox.inbox_id, to=[BUYER_EMAIL],
                            subject=subject, text=args["report_body"],
                        )
                else:
                    sent = agentmail.inboxes.messages.send(
                        inbox_id=inbox.inbox_id, to=[BUYER_EMAIL],
                        subject=subject, text=args["report_body"],
                    )
                    # Save the buyer thread for future round summaries
                    state["buyer_thread_id"] = getattr(sent, "thread_id", None) or getattr(sent, "message_id", "")
            except Exception as e:
                print(f"  ! sending round summary failed: {e}")
                return

            state["round_summary_sent_for_round"] = state.get("current_round", 1)
            state["current_round"] = state.get("current_round", 1) + 1
            save_state(state)
            alert = " [TARGET HIT]" if args.get("target_hit_alert") else ""
            print(f"  ✅ round summary sent to {BUYER_EMAIL}{alert}")
            return


# --- main loop ----------------------------------------------------------------


def main():
    deal_state = deal.load()
    if not deal_state:
        print("ERROR: deal.json not found or empty. Run `cp deal.example.json deal.json` and edit it.")
        return

    inbox = get_or_create_inbox()
    print(f"\n📬 Negotiation agent live at: {inbox.email}")
    print(f"   Buyer: {BUYER_EMAIL}")
    print(f"   Negotiating: {deal_state.get('what', '?')}")
    print(f"   Ideal: {deal_state.get('ideal_price')} {deal_state.get('currency', 'USD')}, "
          f"max: {deal_state.get('max_price')} {deal_state.get('currency', 'USD')}")
    print(f"   Counterparties: {len(deal_state.get('counterparties', []))}")
    print(f"   Polling every {POLL_INTERVAL}s. Ctrl-C to stop.\n")

    state = load_state()
    state.setdefault("current_round", 1)
    save_state(state)

    seen: set[str] = set()

    while True:
        try:
            # 1) Send opening to any queued counterparties
            for cp in deal.queued_counterparties():
                try:
                    send_opening(cp, inbox)
                except Exception as e:
                    print(f"  ! opening failed for {cp['email']}: {e}")

            # 2) Process new replies
            resp = agentmail.inboxes.messages.list(inbox.inbox_id, labels=["unread"])
            new_msgs = [m for m in (resp.messages or []) if m.message_id not in seen]
            for m in new_msgs:
                seen.add(m.message_id)
                if _sender_email(m) == inbox.email.lower():
                    continue

                # Classify sender by thread first (counterparty vs buyer)
                cp = deal.get_counterparty_by_thread(m.thread_id)
                if cp:
                    print(f"\n📩 from {_sender_email(m)} (counterparty {cp['name']})")
                    try:
                        process_counterparty_reply(m, inbox, cp)
                    except Exception as e:
                        print(f"  ! cp-reply error: {e}")
                elif _sender_email(m) == BUYER_EMAIL:
                    print(f"\n📩 from {_sender_email(m)} (buyer strategy)")
                    try:
                        process_buyer_reply(m, inbox)
                    except Exception as e:
                        print(f"  ! buyer-reply error: {e}")
                else:
                    print(f"\n📩 unknown sender {_sender_email(m)}, skipping")
                    _mark_read(inbox.inbox_id, m.message_id, add_labels=["unknown"])

            # 3) Maybe send a round summary
            maybe_send_round_summary(inbox)

        except Exception as e:
            print(f"poll error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
