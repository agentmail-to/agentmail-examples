"""
AgentMail Docs Assistant — answers questions from your docs, escalates the rest.

Workflow:
  1. Create (or reuse) an AgentMail inbox.
  2. Poll for new questions every POLL_INTERVAL seconds.
  3. For each question, ask Claude to use the web_search tool (constrained to
     your DOCS_URL domain) and either reply with a cited answer OR call the
     escalate tool. Escalation forwards the original email to ESCALATION_EMAIL
     and sends a short acknowledgment back to the requester.

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
from urllib.parse import urlparse

from agentmail import AgentMail
from agentmail.inboxes import CreateInboxRequest
from anthropic import Anthropic
from dotenv import load_dotenv

from prompt import build_system_prompt

load_dotenv()

# --- config -------------------------------------------------------------------

AGENTMAIL_API_KEY = os.environ["AGENTMAIL_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
PRODUCT_NAME = os.getenv("PRODUCT_NAME", "the product")
DOCS_URL = os.environ["DOCS_URL"]
ESCALATION_EMAIL = os.environ["ESCALATION_EMAIL"]
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))
MAX_SEARCHES = int(os.getenv("MAX_SEARCHES_PER_QUESTION", "5"))
INBOX_USERNAME = os.getenv("INBOX_USERNAME") or None

STATE_FILE = Path(".agent_state.json")

# Extract bare domain from DOCS_URL (e.g. https://docs.example.com/foo → docs.example.com)
DOCS_DOMAIN = urlparse(DOCS_URL).netloc or DOCS_URL

# --- clients ------------------------------------------------------------------

agentmail = AgentMail(api_key=AGENTMAIL_API_KEY)
claude = Anthropic(api_key=ANTHROPIC_API_KEY)


# --- Claude tools -------------------------------------------------------------

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "allowed_domains": [DOCS_DOMAIN],
    "max_uses": MAX_SEARCHES,
}

ESCALATE_TOOL = {
    "name": "escalate",
    "description": (
        "Call this when the docs do not contain the answer after a real search. "
        "The original email will be forwarded to the escalation team with the "
        "reason you provide. Do NOT call this without first searching the docs."
    ),
    "input_schema": {
        "type": "object",
        "required": ["reason"],
        "properties": {
            "reason": {
                "type": "string",
                "description": "One-sentence summary of what you searched for and why the docs didn't cover it. Goes in the cover note of the forwarded email.",
            },
        },
    },
}


# --- helpers ------------------------------------------------------------------


def _sender_email(message) -> str:
    sender = getattr(message, "from_", None) or getattr(message, "from", None) or ""
    _, email = parseaddr(str(sender))
    return email.lower()


def get_or_create_inbox():
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
            display_name=f"{PRODUCT_NAME} docs assistant",
        )
    )
    STATE_FILE.write_text(
        json.dumps({"inbox_id": inbox.inbox_id, "email": inbox.email}, indent=2)
    )
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


def extract_text_and_citations(content_blocks):
    """Pull the assistant text + dedup'd citation URLs out of the response."""
    text_parts = []
    citation_urls = []
    escalate_args = None

    for block in content_blocks:
        if block.type == "text":
            text_parts.append(block.text)
            for c in (getattr(block, "citations", None) or []):
                url = getattr(c, "url", None)
                if url:
                    citation_urls.append(url)
        elif block.type == "tool_use" and block.name == "escalate":
            escalate_args = block.input

    text = "\n\n".join(text_parts).strip()
    # Dedup citations preserving order
    citation_urls = list(dict.fromkeys(citation_urls))
    return text, citation_urls, escalate_args


def format_reply(text: str, citations: list[str]) -> str:
    if not citations:
        return text
    label = "Source" if len(citations) == 1 else "Sources"
    cited = "\n".join(f"  • {u}" for u in citations)
    return f"{text}\n\n📖 {label}:\n{cited}"


# --- core processing ----------------------------------------------------------


def process_message(message, inbox):
    print(f"  → fetching thread {message.thread_id}")
    thread = agentmail.inboxes.threads.get(inbox.inbox_id, message.thread_id)

    if thread.messages and _sender_email(thread.messages[-1]) == inbox.email.lower():
        if message.message_id != thread.messages[-1].message_id:
            print("  → thread already replied; marking read and skipping")
            _mark_read(inbox.inbox_id, message.message_id)
            return

    conversation = thread_to_messages(thread, inbox.email)
    if not conversation or conversation[-1]["role"] != "user":
        print("  ! no user content to act on")
        _mark_read(inbox.inbox_id, message.message_id)
        return

    system_prompt = build_system_prompt(inbox_email=inbox.email)

    print(f"  → asking Claude (model={MODEL}, web_search → {DOCS_DOMAIN})")
    response = claude.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system_prompt,
        tools=[WEB_SEARCH_TOOL, ESCALATE_TOOL],
        messages=conversation,
    )

    text, citations, escalate_args = extract_text_and_citations(response.content)
    if not text:
        text = "Looking into this — will get back to you shortly."

    requester = _sender_email(message)

    if escalate_args:
        reason = escalate_args.get("reason", "Unable to answer from the docs.")
        print(f"  ⚠️  escalating to {ESCALATION_EMAIL}: {reason}")
        try:
            agentmail.inboxes.messages.forward(
                inbox.inbox_id,
                message.message_id,
                to=[ESCALATION_EMAIL],
                text=f"Couldn't answer from the docs.\n\nAgent's note: {reason}",
            )
        except Exception as e:
            print(f"  ! escalation forward failed: {e}")

        # Send a short acknowledgment back to the requester
        ack = text or "Thanks for reaching out — I'm looping in the team to take a closer look. They'll be in touch."
        agentmail.inboxes.messages.reply(
            inbox.inbox_id, message.message_id, text=ack
        )
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["escalated"])
    else:
        reply = format_reply(text, citations)
        print(f"  → replying ({len(reply)} chars, {len(citations)} citation(s))")
        agentmail.inboxes.messages.reply(
            inbox.inbox_id, message.message_id, text=reply
        )
        _mark_read(inbox.inbox_id, message.message_id, add_labels=["answered"])


# --- main loop ----------------------------------------------------------------


def main():
    inbox = get_or_create_inbox()
    print(f"\n📬 Docs assistant live at: {inbox.email}")
    print(f"   Searching: {DOCS_URL} (domain: {DOCS_DOMAIN})")
    print(f"   Escalating to: {ESCALATION_EMAIL}")
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
        except Exception as e:
            print(f"poll error: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
