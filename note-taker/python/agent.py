"""
AgentMail Personal Note Taker.

Per incoming email, Claude calls EXACTLY ONE of three tools:

  extract_note(...)
      → save Markdown note to notes/<YYYY-MM-DD>-<slug>.md (with YAML frontmatter)
      → append action items to actions.csv
      → reply to user with summary + permalink + action items

  search_notes(query)
      → run keyword/tag search across notes/
      → second Claude turn composes the answer using matched notes
      → reply to user with the composed answer

  discard(reason)
      → newsletter / auto-gen — silently mark read

Special: if a reply contains the word "done" on the first line, the agent
finds the original note via the thread and marks all its actions complete.

Once per loop:
  - Fire reminders for actions whose deadline is within REMINDER_HOURS
  - Send Friday digest at DIGEST_WEEKDAY/DIGEST_HOUR (default Fri 17:00)

Run:
    pip install -r requirements.txt
    cp .env.example .env
    python agent.py
"""

import json
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path

from agentmail import AgentMail
from agentmail.inboxes import CreateInboxRequest
from anthropic import Anthropic
from dotenv import load_dotenv

import actions as actions_mod
import notes_store
import scheduler
from prompt import build_classify_prompt, build_search_compose_prompt

load_dotenv()

# --- config -------------------------------------------------------------------

AGENTMAIL_API_KEY = os.environ["AGENTMAIL_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
USER_NAME = os.getenv("USER_NAME", "User")
USER_EMAIL = os.environ["USER_EMAIL"]
NOTIFY_ASSIGNEES = os.getenv("NOTIFY_ASSIGNEES", "false").lower() == "true"
DIGEST_HOUR = int(os.getenv("DIGEST_HOUR", "17"))
DIGEST_WEEKDAY = int(os.getenv("DIGEST_WEEKDAY", "4"))
REMINDER_HOURS = float(os.getenv("REMINDER_HOURS", "24"))
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "15"))
INBOX_USERNAME = os.getenv("INBOX_USERNAME") or None

STATE_FILE = Path(".agent_state.json")

# --- clients ------------------------------------------------------------------

agentmail = AgentMail(api_key=AGENTMAIL_API_KEY)
claude = Anthropic(api_key=ANTHROPIC_API_KEY)


# --- Claude tools -------------------------------------------------------------

EXTRACT_NOTE_TOOL = {
    "name": "extract_note",
    "description": "Save the email content as a structured note. Use for emails the user wants to remember.",
    "input_schema": {
        "type": "object",
        "required": ["summary", "tags", "source_summary"],
        "properties": {
            "summary": {"type": "string", "description": "One paragraph, ≤60 words."},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "1-4 short topical labels (lowercase)."},
            "source_summary": {"type": "string", "description": 'e.g. "Fwd from Sarah Chen, 2026-04-29"'},
            "decisions": {"type": "array", "items": {"type": "string"}},
            "action_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["task"],
                    "properties": {
                        "owner": {"type": "string", "description": "Name or email of the assignee. Empty if unassigned."},
                        "task": {"type": "string"},
                        "deadline": {"type": "string", "description": 'ISO date "YYYY-MM-DD" or empty.'},
                        "urgency": {"type": "string", "enum": ["high", "medium", "low"]},
                    },
                },
            },
            "open_questions": {"type": "array", "items": {"type": "string"}},
            "key_facts": {"type": "array", "items": {"type": "string"}},
        },
    },
}

SEARCH_NOTES_TOOL = {
    "name": "search_notes",
    "description": "Search the user's past notes to answer a question they emailed.",
    "input_schema": {
        "type": "object",
        "required": ["query"],
        "properties": {"query": {"type": "string", "description": "The user's question, verbatim or lightly cleaned."}},
    },
}

DISCARD_TOOL = {
    "name": "discard",
    "description": "Newsletter, auto-gen, or otherwise not worth saving.",
    "input_schema": {
        "type": "object",
        "required": ["reason"],
        "properties": {"reason": {"type": "string"}},
    },
}

CLASSIFY_TOOLS = [EXTRACT_NOTE_TOOL, SEARCH_NOTES_TOOL, DISCARD_TOOL]


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
            display_name=f"{USER_NAME} Notes",
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


def _is_completion_reply(text: str) -> bool:
    """Did the user just reply 'done' / 'complete' to a note thread?"""
    if not text:
        return False
    first_line = text.strip().splitlines()[0].strip().lower() if text.strip() else ""
    # Strip trailing punctuation
    first_line = re.sub(r"[!.\s]+$", "", first_line)
    return first_line in {"done", "complete", "completed", "finished", "✓"}


# --- formatting ---------------------------------------------------------------


def _format_note_reply(note_path: Path, args: dict, new_actions: list[dict]) -> str:
    summary = args.get("summary", "")
    tags = args.get("tags", []) or []
    decisions = args.get("decisions", []) or []
    open_qs = args.get("open_questions", []) or []
    key_facts = args.get("key_facts", []) or []

    lines = [
        f"Saved note → {note_path}",
        "",
        f"Tags: {', '.join(tags) if tags else '(none)'}",
        "",
        summary,
        "",
    ]
    if decisions:
        lines += ["Decisions:"] + [f"  • {d}" for d in decisions] + [""]
    if new_actions:
        lines.append("Action items:")
        for ai in new_actions:
            owner = ai.get("owner") or "(unassigned)"
            deadline = ai.get("deadline") or ""
            urg = ai.get("urgency") or ""
            tail = f" — {deadline} · {urg}" if (deadline or urg) else ""
            lines.append(f"  • [{owner}] {ai['task']}{tail}")
        lines.append("")
    if open_qs:
        lines += ["Open questions:"] + [f"  • {q}" for q in open_qs] + [""]
    if key_facts:
        lines += ["Key facts:"] + [f"  • {f}" for f in key_facts] + [""]
    lines.append("Reply 'done' to mark all action items in this note complete.")
    lines.append("")
    lines.append("— Notes assistant")
    return "\n".join(lines)


# --- search agent (two-turn) --------------------------------------------------


def _run_search(query: str, inbox_email: str) -> str:
    """Search notes for query, then ask Claude to compose an answer."""
    matches = notes_store.search(query, limit=8)

    if not matches:
        # Pre-compose a "no results" reply without burning a Claude call
        return (
            f"I couldn't find any notes matching that. You currently have "
            f"{len(notes_store.list_all())} saved notes. Try narrowing the "
            f"query or check your tags.\n\n— Notes assistant"
        )

    # Build a compact context block of the top matches
    context_blocks = []
    for m in matches:
        excerpt = notes_store.read_note_excerpt(m["path"], max_chars=800)
        context_blocks.append(
            f"=== {m['path']} ===\n"
            f"date: {m['date']}  ·  tags: {', '.join(m['tags'])}\n"
            f"source: {m['source']}\n\n"
            f"{excerpt}"
        )
    context = "\n\n".join(context_blocks)

    response = claude.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=build_search_compose_prompt(inbox_email),
        messages=[{
            "role": "user",
            "content": (
                f"User question:\n{query}\n\n"
                f"Top matching notes:\n\n{context}\n\n"
                f"Compose your reply now."
            ),
        }],
    )
    # Claude returned plain text on this turn (no tools)
    text_blocks = [b.text for b in response.content if hasattr(b, "text")]
    return "\n".join(text_blocks).strip() or "(empty response)"


# --- core processing ----------------------------------------------------------


def process_message(message, inbox):
    full = agentmail.inboxes.messages.get(inbox.inbox_id, message.message_id)
    extracted = (getattr(full, "extracted_text", None) or "").strip()
    raw = (full.text or "").strip()
    body = raw if len(raw) > len(extracted) * 1.5 else (extracted or raw)

    sender = _sender_email(message)
    subject = getattr(message, "subject", "") or ""
    thread_id = getattr(full, "thread_id", "") or ""
    print(f"  → {sender}  ·  '{subject[:60]}'  ·  thread {thread_id[:24]}")

    # Skip our own outgoing replies (they come back as inbound mail when the
    # user replies to themselves on the thread)
    if sender == inbox.email.lower():
        print("  · skipping our own outgoing reply")
        _mark_read(inbox.inbox_id, message.message_id)
        return

    # Special-case: "done" reply to a note thread → close out its actions
    if _is_completion_reply(body):
        existing = notes_store.find_by_thread(thread_id)
        if existing:
            n = actions_mod.mark_done_for_note(str(existing))
            print(f"  ✓ marked {n} action(s) done for {existing}")
            try:
                agentmail.inboxes.messages.reply(
                    inbox.inbox_id, message.message_id,
                    text=f"Marked {n} action item(s) as done for {existing}.\n\n— Notes assistant",
                )
            except Exception as e:
                print(f"  ! couldn't ack completion: {e}")
            _mark_read(inbox.inbox_id, message.message_id, add_labels=["completed"])
            return

    # Classify
    response = claude.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=build_classify_prompt(inbox_email=inbox.email),
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
        print("  ! Claude returned no tool call, skipping")
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["error"])
        return

    name = tool_use.name
    args = tool_use.input or {}
    print(f"  ✓ classification: {name}")

    if name == "extract_note":
        existing = notes_store.find_by_thread(thread_id) if thread_id else None
        path = notes_store.write_note(
            source_summary=args.get("source_summary", "") or f"From {sender}",
            thread_id=thread_id,
            tags=args.get("tags", []) or [],
            summary=args.get("summary", ""),
            decisions=args.get("decisions", []) or [],
            action_items=args.get("action_items", []) or [],
            open_questions=args.get("open_questions", []) or [],
            key_facts=args.get("key_facts", []) or [],
            existing_path=existing,
        )
        new_actions = actions_mod.append_from_note(str(path), args.get("action_items", []) or [])
        print(f"  ✓ saved note: {path}  (+{len(new_actions)} actions)")
        try:
            agentmail.inboxes.messages.reply(
                inbox.inbox_id, message.message_id,
                text=_format_note_reply(path, args, new_actions),
            )
        except Exception as e:
            print(f"  ! reply failed: {e}")
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["note"])

    elif name == "search_notes":
        query = args.get("query", "") or body
        answer = _run_search(query, inbox.email)
        try:
            agentmail.inboxes.messages.reply(
                inbox.inbox_id, message.message_id,
                text=answer,
            )
        except Exception as e:
            print(f"  ! search reply failed: {e}")
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["search"])

    else:  # discard
        reason = args.get("reason", "noise")
        print(f"  · discarded ({reason})")
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["discarded"])


# --- main loop ----------------------------------------------------------------


def main():
    print(f"--- Personal Note Taker  ·  {USER_NAME} ---")
    inbox = get_or_create_inbox()
    print(f"Inbox: {inbox.email}  (id: {inbox.inbox_id})")
    print(f"User:  {USER_EMAIL}")
    print(f"Polling every {POLL_INTERVAL}s.")
    print(f"Reminders: {REMINDER_HOURS}h before deadline. Notify assignees: {NOTIFY_ASSIGNEES}.")
    if DIGEST_WEEKDAY >= 0:
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        print(f"Digest: {days[DIGEST_WEEKDAY]} {DIGEST_HOUR}:00")
    print()

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

            scheduler.fire_due_reminders(
                agentmail_client=agentmail, inbox=inbox,
                user_email=USER_EMAIL, reminder_hours=REMINDER_HOURS,
                notify_assignees=NOTIFY_ASSIGNEES,
            )
            scheduler.maybe_send_digest(
                agentmail_client=agentmail, inbox=inbox,
                user_email=USER_EMAIL, hour=DIGEST_HOUR, weekday=DIGEST_WEEKDAY,
            )

        except Exception as e:
            print(f"! poll loop error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
