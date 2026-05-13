"""
AgentMail Newsletter Digest — daily digest from your inbox.

Workflow:
  1. Create (or reuse) an AgentMail inbox. Forward your newsletters there.
  2. Poll for new mail. For each new email, ask Claude to either summarize
     (newsletter) or skip (everything else).
  3. Cache summaries to newsletter_cache.json.
  4. Once per day at DIGEST_TIME, ask Claude to dedupe + rank by
     USER_INTERESTS + format the top 5-8, and email the digest to USER_EMAIL.

Run:
    pip install -r requirements.txt
    cp .env.example .env   # fill in keys, USER_INTERESTS, DIGEST_TIME
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

from digest import is_digest_due, send_digest
from newsletter_cache import append_item
from prompt import build_summarize_prompt

load_dotenv()

# --- config -------------------------------------------------------------------

AGENTMAIL_API_KEY = os.environ["AGENTMAIL_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
USER_NAME = os.getenv("USER_NAME", "the user")
USER_EMAIL = os.environ["USER_EMAIL"]
DIGEST_TIME = os.getenv("DIGEST_TIME", "08:00")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
INBOX_USERNAME = os.getenv("INBOX_USERNAME") or None

STATE_FILE = Path(".agent_state.json")

# --- clients ------------------------------------------------------------------

agentmail = AgentMail(api_key=AGENTMAIL_API_KEY)
claude = Anthropic(api_key=ANTHROPIC_API_KEY)


# --- per-message tools (summarize or skip) ------------------------------------

SAVE_SUMMARY_TOOL = {
    "name": "save_summary",
    "description": "Call this when the email IS a newsletter. Saves a structured summary to the cache for the daily digest.",
    "input_schema": {
        "type": "object",
        "required": ["headline", "key_points", "primary_link", "topic"],
        "properties": {
            "headline": {"type": "string", "description": "ONE crisp line — most interesting/actionable item."},
            "key_points": {"type": "string", "description": "1-3 sentence summary of the substance, specific not generic."},
            "primary_link": {"type": "string", "description": "URL representing the headline. Prefer original source over archive."},
            "topic": {"type": "string", "description": "Short tag like 'ai-research', 'growth', 'dev-tooling'."},
            "importance": {
                "type": "integer",
                "description": "1=interesting, 2=worth surfacing, 3=call-to-action / deadline / personal.",
                "minimum": 1,
                "maximum": 3,
            },
        },
    },
}

SKIP_TOOL = {
    "name": "skip",
    "description": "Call this when the email is NOT a newsletter (transactional, personal, cold outreach, marketing coupon, etc.).",
    "input_schema": {
        "type": "object",
        "required": ["reason"],
        "properties": {
            "reason": {"type": "string"},
        },
    },
}

PER_MESSAGE_TOOLS = [SAVE_SUMMARY_TOOL, SKIP_TOOL]


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
            display_name=f"{USER_NAME}'s newsletter digest",
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


# --- per-message processing ---------------------------------------------------


def process_message(message, inbox):
    """Run Claude with the per-message tools and dispatch the call."""
    print(f"  → fetching message body")
    full = agentmail.inboxes.messages.get(inbox.inbox_id, message.message_id)
    body = (getattr(full, "extracted_text", None) or full.text or "").strip()
    if not body:
        # Try HTML
        html = getattr(full, "extracted_html", None) or full.html
        if html:
            # Crude strip; real parsing happens via tool-driven Claude
            body = html
    if not body:
        print("  ! empty body, skipping")
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["empty"])
        return

    user_payload = (
        f"From: {full.from_}\n"
        f"Subject: {full.subject}\n\n"
        f"---\n"
        f"{body[:8000]}"  # cap for context
    )

    print(f"  → asking Claude (model={MODEL})")
    response = claude.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=build_summarize_prompt(),
        tools=PER_MESSAGE_TOOLS,
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": user_payload}],
    )

    handled = False
    for block in response.content:
        if block.type != "tool_use":
            continue
        if block.name == "save_summary":
            args = block.input
            print(f"  📝 summary saved ({args.get('topic', '?')}): {args.get('headline', '')[:60]}")
            append_item({
                "date_iso": datetime.now(timezone.utc).isoformat(),
                "headline": args.get("headline", ""),
                "key_points": args.get("key_points", ""),
                "primary_link": args.get("primary_link", ""),
                "topic": args.get("topic", ""),
                "importance": args.get("importance", 1),
                "source_subject": full.subject or "",
                "source_from": _sender_email(full),
                "source_message_id": full.message_id,
            })
            _mark_read(inbox.inbox_id, full.message_id, add_labels=["digested", args.get("topic", "newsletter")])
            handled = True
            break
        if block.name == "skip":
            reason = block.input.get("reason", "")
            print(f"  ⏭  skipped: {reason}")
            _mark_read(inbox.inbox_id, full.message_id, add_labels=["skipped"])
            handled = True
            break

    if not handled:
        print("  ! Claude did not call any tool")
        _mark_read(inbox.inbox_id, full.message_id)


# --- main loop ----------------------------------------------------------------


def main():
    inbox = get_or_create_inbox()
    print(f"\n📬 Newsletter digest agent live at: {inbox.email}")
    print(f"   Forward newsletters there to ingest them.")
    print(f"   Daily digest at {DIGEST_TIME} → {USER_EMAIL}")
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
                    continue  # skip our own outgoing digest emails
                print(f"\n📩 from {_sender_email(m)}: {(m.subject or '(no subject)')[:60]}")
                try:
                    process_message(m, inbox)
                except Exception as e:
                    print(f"  ! error processing message: {e}")

            # Daily digest scheduling
            state = load_state()
            if is_digest_due(DIGEST_TIME, state.get("last_digest_date")):
                result = send_digest(claude, agentmail, inbox, MODEL, USER_EMAIL)
                if result["sent"]:
                    print(f"   ✅ sent ({result['item_count']} items)\n")
                else:
                    print(f"   ⏭  skipped: {result.get('reason', '')}\n")
                state["last_digest_date"] = datetime.now().strftime("%Y-%m-%d")
                save_state(state)

        except Exception as e:
            print(f"poll error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
