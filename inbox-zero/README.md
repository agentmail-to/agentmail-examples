# AgentMail Inbox Zero Agent

> Drafts replies while you sleep — wake up to an inbox you just need to skim.

_Part of the [AgentMail templates collection](https://agentmail.to/build/templates) — runnable open-source agents you can clone and ship in minutes._

An agent that lives in an [AgentMail](https://agentmail.to) inbox. It reads each new email, classifies it, and either drafts a reply (in your voice), flags it for your attention, or marks it handled. Once a day at `WAKE_TIME` it sends you a digest of what happened overnight.

Built on **AgentMail + Claude**.

## Pick your language

> **Polling vs webhooks.** This template polls AgentMail every 20s — zero infra, runs from your laptop. For production, switch to webhooks (~10 lines of change). See [Beyond the template](#beyond-the-template).

- [**Python**](./python) — `pip install` and `python agent.py`
- [**TypeScript**](./typescript) — `npm install` and `npm start`

Both versions are functionally identical.

## What you'll need

- An AgentMail API key — https://console.agentmail.to
- An Anthropic API key — https://console.anthropic.com
- Python 3.10+ or Node.js 18+
- A few paragraphs of your own writing for `STYLE_EXAMPLES` — drafts sound like you when the prompt has real samples to mimic

## How it works

1. The agent creates a dedicated AgentMail inbox and prints its address.
2. You forward mail there (or set filters in your real inbox).
3. The polling loop pulls unread mail and asks Claude to call exactly one of three tools per email:
   - `draft_reply(text)` — saves a real draft via AgentMail's drafts API, threaded to the source message
   - `flag_for_human(reason)` — labels for your attention, no draft
   - `mark_handled(category)` — for spam, promotional, FYI, automated notifications
4. Each processed email gets a category label and is marked read.
5. **At `WAKE_TIME` daily, the agent emails you a digest** of every draft it created and every email it flagged — open AgentMail to review and send.

## Customize

- The **system prompt** lives in `prompt.py` / `prompt.ts`. Tweak it to change classification rules or drafting style.
- The **style** the agent writes in is driven by `STYLE_EXAMPLES` in `.env` — paste real samples of your own writing.
- The **digest format** is in `digest.py` / `digest.ts`.

## Beyond the template

This template uses polling because it works the moment you `python agent.py` — no public URL, no ngrok, no deploy. The two upgrade paths when you outgrow that:

### Upgrade to webhooks (recommended for production)

```python
# 1. Subscribe (run once)
client.webhooks.create(
    url="https://your-domain.com/agentmail-webhook",
    event_types=["message.received"],
)

# 2. Receive (FastAPI / Express / whatever)
@app.post("/agentmail-webhook")
async def webhook(request: Request):
    payload = await request.json()
    if payload["event_type"] == "message.received":
        process_message(payload["message"], inbox)
    return {"ok": True}
```

HMAC-verify with `webhook.secret`. See the [AgentMail webhook docs](https://docs.agentmail.to).

### Or use the websocket client

```python
async with client.websockets.connect() as ws:
    async for event in ws:
        if event.event_type == "message.received":
            process_message(event.message, inbox)
```

### Other ideas

- **Real style matching** — replace static `STYLE_EXAMPLES` with your last 50 sent emails pulled from Gmail / Outlook.
- **Quiet hours** — only act on mail received outside your working hours.
- **One-click send** — wire up a "reply YES to send" flow so you can approve drafts from the digest email itself.
- **Per-sender rules** — VIP senders always get drafts, mailing lists always get marked handled.

## License

MIT
