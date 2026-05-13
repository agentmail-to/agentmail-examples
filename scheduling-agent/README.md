# AgentMail Scheduling Agent

> Email your agent to book time — it knows your rules.

_Part of the [AgentMail templates collection](https://agentmail.to/build/templates) — runnable open-source agents you can clone and ship in minutes._

A simple scheduling agent that lives in an [AgentMail](https://agentmail.to) inbox. People email it to book time with you, and it negotiates back-and-forth using rules you define (sales days, internal days, blocked days, max per day, etc.).

Built on **AgentMail + Claude**.

## Pick your language

> **Polling vs webhooks.** This template polls AgentMail every 10s for new mail — zero infra, runs from your laptop. For production, switch to webhooks (`client.webhooks.create(url=..., event_types=["message.received"])`) so AgentMail pushes new mail to your endpoint with no polling lag and no wasted API calls. See [Beyond the template](#beyond-the-template) for the upgrade path.


- [**Python**](./python) — `pip install` and `python agent.py`
- [**TypeScript**](./typescript) — `npm install` and `npm start`

Both versions are functionally identical. Pick whichever matches your stack.

## What you'll need

- An AgentMail API key — https://console.agentmail.to
- An Anthropic API key — https://console.anthropic.com
- Python 3.10+ or Node.js 18+

## How it works

1. The agent creates a dedicated AgentMail inbox and prints its address.
2. It polls for unread messages.
3. Each new message goes to Claude with the scheduling system prompt + the full thread history.
4. Claude classifies the request (sales / internal / personal), checks your rules, and replies with available slots.
5. **Once a slot is confirmed, the agent attaches an `.ics` calendar invite to the reply.** Gmail, Outlook, and Apple Mail all auto-detect it and surface a one-click "Add to calendar" prompt — for both you (CC'd on every reply) and the requester. No Google Calendar OAuth required.

## Customize

- The **system prompt** lives in `prompt.py` / `prompt.ts`. Tweak it to change the agent's tone, add new rule types, or change the booking flow.
- The **rules themselves** are configured via `.env`.

## Beyond the template

This template uses polling because it works the moment you `python agent.py` — no public URL, no ngrok, no deploy. The two upgrade paths when you outgrow that:

### Upgrade to webhooks (recommended for production)

AgentMail webhooks push new mail to your endpoint the moment it arrives. No polling lag, no wasted API calls. Roughly a 10-line change:

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
        # payload["message"] is the full Message object — no second fetch needed
        process_message(payload["message"], inbox)
    return {"ok": True}
```

You'll want HMAC signature verification against `webhook.secret` — see the [AgentMail webhook docs](https://docs.agentmail.to).

### Or use the websocket client

Low-latency streaming with no public URL needed (good for laptops behind NAT):

```python
async with client.websockets.connect() as ws:
    async for event in ws:
        if event.event_type == "message.received":
            process_message(event.message, inbox)
```

### Other ideas

- **Connect a real calendar API** — the .ics attachment is universal, but it doesn't sync your availability. Hook in Google Calendar / Outlook to actually check free/busy before offering slots.
- **Persist conversation state** — currently every reply re-fetches the thread. For high-volume inboxes, cache it.

## License

MIT
