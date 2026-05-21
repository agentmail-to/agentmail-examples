"""
AgentMail Sales Signal Router — classifies inbound mail and fires Slack alerts.

Per incoming email, Claude calls EXACTLY ONE of four tools:

  hot_reply(sentiment, summary, deal_owner_hint)
      → human reply on a sales thread with buying intent / objection / OOO / unsub
      → fires Slack DM to the rep (looked up via watchlist.deal_owners)
      → labels the email `signal-hot`

  crm_notification(event_type, deal_size_usd, customer, summary)
      → Stripe / HubSpot / Salesforce-style automated event
      → tiers by deal size (enterprise / mid_market / smb)
      → enterprise tier → SLACK_WEBHOOK_ENTERPRISE
      → labels `signal-crm`

  watchlist_match(matched_term, why, summary)
      → sender or keyword on the watchlist (and not already crm/hot)
      → fires Slack alert to the default channel
      → labels `signal-watchlist`

  noise(reason)
      → marketing, internal, OOO without a thread, etc.
      → no Slack, just logs + label `signal-noise`

Every classification appends a row to signals.csv. Once per day at DIGEST_HOUR
(local), an EOD digest is built from today's rows and sent to SALES_LEAD_EMAIL
+ posted to Slack.

Run:
    pip install -r requirements.txt
    cp .env.example .env                              # fill API keys + Slack URL
    cp watchlist.example.json watchlist.json          # configure your watchlist
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

import digest as digest_mod
import signals as signals_mod
import slack as slack_mod
import watchlist as watchlist_mod
from prompt import build_system_prompt

load_dotenv()

# --- config -------------------------------------------------------------------

AGENTMAIL_API_KEY = os.environ["AGENTMAIL_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
COMPANY_NAME = os.getenv("COMPANY_NAME", "Sales")
SALES_LEAD_EMAIL = os.getenv("SALES_LEAD_EMAIL", "")
ENTERPRISE_THRESHOLD = float(os.getenv("ENTERPRISE_THRESHOLD", "100000"))
MID_MARKET_THRESHOLD = float(os.getenv("MID_MARKET_THRESHOLD", "10000"))
DIGEST_HOUR = int(os.getenv("DIGEST_HOUR", "17"))
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "15"))
INBOX_USERNAME = os.getenv("INBOX_USERNAME") or None

if not os.getenv("SLACK_WEBHOOK_URL"):
    print("⚠️  SLACK_WEBHOOK_URL not set — alerts will be skipped.")

STATE_FILE = Path(".agent_state.json")

# --- clients ------------------------------------------------------------------

agentmail = AgentMail(api_key=AGENTMAIL_API_KEY)
claude = Anthropic(api_key=ANTHROPIC_API_KEY)


# --- Claude tools -------------------------------------------------------------

TOOLS = [
    {
        "name": "hot_reply",
        "description": "A human reply on a sales thread showing buying intent, objection, unsubscribe, or out-of-office. Triggers an instant Slack DM to the rep.",
        "input_schema": {
            "type": "object",
            "required": ["sentiment", "summary"],
            "properties": {
                "sentiment": {
                    "type": "string",
                    "enum": ["positive", "objection", "unsubscribe", "ooo"],
                    "description": "positive=buying intent, objection=worth the rep's time, unsubscribe=opt-out request, ooo=out of office",
                },
                "summary": {
                    "type": "string",
                    "description": "One-line description of why this fired — what they said.",
                },
                "deal_owner_hint": {
                    "type": "string",
                    "description": "Apparent rep on the thread (from sig/cc) if obvious, else empty.",
                },
            },
        },
    },
    {
        "name": "crm_notification",
        "description": "Automated event from a CRM/billing system (Stripe, HubSpot, Salesforce, Chargebee, Pipedrive, etc.).",
        "input_schema": {
            "type": "object",
            "required": ["event_type", "summary"],
            "properties": {
                "event_type": {
                    "type": "string",
                    "enum": [
                        "deal_closed_won", "deal_closed_lost",
                        "invoice_paid", "first_invoice",
                        "subscription_started", "subscription_upgraded",
                        "subscription_canceled", "churn",
                        "mrr_change",
                    ],
                },
                "deal_size_usd": {
                    "type": "number",
                    "description": "Dollar amount in USD (convert non-USD: EUR×1.08, GBP×1.26, CAD×0.74). 0 if not extractable.",
                },
                "customer": {
                    "type": "string",
                    "description": "Customer name or domain.",
                },
                "summary": {
                    "type": "string",
                    "description": "One-line summary quoting the operative line.",
                },
            },
        },
    },
    {
        "name": "watchlist_match",
        "description": "Email matches the watchlist (domain/keyword/sender) but isn't already a hot_reply or crm_notification.",
        "input_schema": {
            "type": "object",
            "required": ["matched_term", "why", "summary"],
            "properties": {
                "matched_term": {"type": "string", "description": "The specific watchlist entry that matched."},
                "why": {"type": "string", "description": "One-line reason for the match."},
                "summary": {"type": "string"},
            },
        },
    },
    {
        "name": "noise",
        "description": "None of the above — newsletter, internal, marketing, delivery status, etc.",
        "input_schema": {
            "type": "object",
            "required": ["reason"],
            "properties": {"reason": {"type": "string", "description": "Short tag — newsletter / internal / delivery_status / marketing / other"}},
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
            display_name=f"{COMPANY_NAME} Sales Signals",
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


def _tier_for(amount_usd: float) -> str:
    if amount_usd >= ENTERPRISE_THRESHOLD:
        return "enterprise"
    if amount_usd >= MID_MARKET_THRESHOLD:
        return "mid_market"
    return "smb"


# --- core processing ----------------------------------------------------------


def process_message(message, inbox):
    full = agentmail.inboxes.messages.get(inbox.inbox_id, message.message_id)

    # Prefer the longer of extracted_text vs raw text — extracted_text strips
    # quoted history but sometimes drops the live body too.
    extracted = (getattr(full, "extracted_text", None) or "").strip()
    raw = (full.text or "").strip()
    body = raw if len(raw) > len(extracted) * 1.5 else (extracted or raw)

    sender = _sender_email(message)
    subject = getattr(message, "subject", "") or ""
    print(f"  → {sender}  ·  '{subject[:60]}'")

    # Reload watchlist on every email — supports live edits
    wl = watchlist_mod.load()

    user_message = (
        f"From: {sender}\n"
        f"Subject: {subject}\n\n"
        f"---WATCHLIST CONTEXT---\n{watchlist_mod.context_block(wl)}\n\n"
        f"---EMAIL BODY---\n{body[:6000] if body else '(empty)'}"
    )

    response = claude.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=build_system_prompt(inbox_email=inbox.email),
        tools=TOOLS,
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": user_message}],
    )

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if not tool_use:
        print("  ! Claude returned no tool call, skipping")
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["signal-error"])
        return

    classification = tool_use.name
    args = tool_use.input or {}
    print(f"  ✓ classification: {classification}  args: {json.dumps(args)[:200]}")

    slack_fired = False
    label = f"signal-{classification.replace('_', '-').replace('notification', 'crm')}"
    sentiment_or_event = ""
    amount_usd = 0.0
    customer = ""
    summary = args.get("summary", "") or args.get("reason", "") or ""

    if classification == "hot_reply":
        sentiment = args.get("sentiment", "")
        sentiment_or_event = sentiment
        owner_slack_id = watchlist_mod.find_owner(wl, sender, body)
        slack_fired = slack_mod.hot_reply_alert(
            sender=sender, summary=summary, sentiment=sentiment,
            deal_owner_slack_id=owner_slack_id,
        )
        label = "signal-hot"

    elif classification == "crm_notification":
        event_type = args.get("event_type", "")
        amount_usd = float(args.get("deal_size_usd", 0) or 0)
        customer = args.get("customer", "")
        tier = _tier_for(amount_usd)
        sentiment_or_event = event_type
        slack_fired = slack_mod.crm_event_alert(
            sender=sender, event_type=event_type, customer=customer,
            deal_size_usd=amount_usd, tier=tier, summary=summary,
        )
        label = "signal-crm"

    elif classification == "watchlist_match":
        matched_term = args.get("matched_term", "")
        sentiment_or_event = matched_term
        slack_fired = slack_mod.watchlist_alert(
            sender=sender, matched_term=matched_term,
            why=args.get("why", ""), summary=summary,
        )
        label = "signal-watchlist"

    else:  # noise
        sentiment_or_event = args.get("reason", "")
        label = "signal-noise"

    signals_mod.log(
        message_id=message.message_id, sender=sender,
        classification=classification, sentiment_or_event=sentiment_or_event,
        amount_usd=amount_usd, customer=customer, summary=summary,
        slack_fired=slack_fired,
    )

    _mark_read(inbox.inbox_id, message.message_id, add_labels=[label])


# --- main loop ----------------------------------------------------------------


def main():
    print(f"--- Sales Signal Router  ·  {COMPANY_NAME} ---")
    inbox = get_or_create_inbox()
    print(f"Inbox: {inbox.email}  (id: {inbox.inbox_id})")
    print(f"Polling every {POLL_INTERVAL}s. Digest at {DIGEST_HOUR}:00 daily.\n")

    while True:
        try:
            unread = agentmail.inboxes.messages.list(inbox.inbox_id, labels=["unread"])
            messages = unread.messages or []
            if messages:
                print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {len(messages)} unread")
                for m in messages:
                    try:
                        process_message(m, inbox)
                    except Exception as e:
                        print(f"  ! error on {m.message_id}: {e}")

            digest_mod.maybe_send(
                agentmail_client=agentmail, inbox=inbox,
                sales_lead_email=SALES_LEAD_EMAIL, hour=DIGEST_HOUR,
            )

        except Exception as e:
            print(f"! poll loop error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
