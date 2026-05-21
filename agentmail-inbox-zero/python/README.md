# Inbox Zero Agent — Python

An agent that watches your inbox while you sleep and **drafts replies for you to review in the morning**. Built on [AgentMail](https://agentmail.to) + Claude.

> **Polling vs webhooks.** This template polls AgentMail every 20s — zero infra, runs from your laptop. For production, switch to webhooks (~10 lines of change). See [Beyond this template](#beyond-this-template).

## Setup (3 minutes)

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in:
   - `AGENTMAIL_API_KEY` — from https://console.agentmail.to
   - `ANTHROPIC_API_KEY` — from https://console.anthropic.com
   - `USER_NAME`, `USER_EMAIL`, `TIMEZONE`
   - `STYLE_EXAMPLES` — **important** — paste a few paragraphs of your own writing so drafts sound like you. Generic instructions don't work as well as real examples.
   - `WAKE_TIME` — when to send the morning digest (default `08:00`)

3. **Run**
   ```bash
   python agent.py
   ```
   On first run the agent creates a fresh AgentMail inbox and prints the address. **Forward mail there** (or set up filters in your real inbox to forward) to start drafting.

## How it works

1. The polling loop pulls unread mail every `POLL_INTERVAL_SECONDS`.
2. For each new email, the agent fetches the full thread and asks Claude to choose exactly one of three tools:
   - `draft_reply(text)` — save a draft reply (using AgentMail's drafts API, threaded via `in_reply_to`)
   - `flag_for_human(reason)` — label the message for your attention; no draft
   - `mark_handled(category)` — for spam, promotional, FYI, or automated notifications
3. Each processed email is marked read with a category label so it doesn't get re-processed.
4. At `WAKE_TIME` each day, the agent sends a digest email to `USER_EMAIL` listing every draft created and every email flagged for your attention.

## Files

| File | What it does |
| --- | --- |
| `agent.py` | Polling loop + tool dispatch + digest scheduling. |
| `prompt.py` | System prompt template. Edit to change classification rules or drafting style. |
| `digest.py` | Builds the morning digest email body and decides when to send. |
| `.env.example` | Copy to `.env` and fill in. Includes a starter `STYLE_EXAMPLES` block. |

## What gets drafted vs flagged vs handled

The agent classifies each email per the rules in `prompt.py`:

- **Draft a reply** — questions, requests, scheduling, replies needed
- **Flag for human** — anything requiring a decision, commitment, or sensitive judgment (legal, financial, personnel)
- **Mark handled** — spam, promotional, FYI, automated notifications

You can change these by editing the system prompt.

## Beyond this template

### Switch from polling to webhooks (recommended for production)

Polling makes the template easy to clone and run, but in production you want AgentMail to push events to you the moment they arrive. Roughly 10 lines of change:

```python
# 1. Subscribe (run once)
client.webhooks.create(
    url="https://your-domain.com/agentmail-webhook",
    event_types=["message.received"],
)

# 2. Replace the polling loop in agent.py with a webhook handler
@app.post("/agentmail-webhook")
async def webhook(request: Request):
    payload = await request.json()
    if payload["event_type"] == "message.received":
        # payload["message"] is the full Message — no second fetch needed
        process_message(payload["message"], inbox)
    return {"ok": True}
```

Use the `secret` returned by `webhooks.create()` to HMAC-verify incoming requests.

### Other upgrades

- **Better style matching** — point `STYLE_EXAMPLES` at your actual sent folder instead of pasting examples. Pull the last 50 sent messages and feed them to Claude as a system message.
- **Quiet hours** — only act on emails received between specific hours (so the agent doesn't draft replies for emails sent during work hours when you'd reply yourself).
- **Send drafts on approval** — wire up a "reply YES to send" flow so you can approve drafts from the digest email itself.
- **Per-sender rules** — VIP senders always get drafts, mailing lists always get marked-handled, etc. Add a sender allowlist/blocklist alongside the LLM classification.
