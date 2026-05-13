# AgentMail Support Agent

> Triage, respond, escalate, follow up, close — all from email.

_Part of the [AgentMail templates collection](https://agentmail.to/build/templates) — runnable open-source agents you can clone and ship in minutes._

A customer support agent that lives in an [AgentMail](https://agentmail.to) inbox. For each incoming email, Claude classifies (`billing` / `bug` / `feature_request` / `general` / `urgent`), then either:

- **Responds** from your knowledge base or help-center docs
- **Escalates** to a human address (with reason + classification) and acknowledges the customer
- **Closes** the ticket when the customer signals they're done

Plus a **48-hour stale-ticket follow-up** so customers waiting on the human team aren't left in silence, and a **`tickets.csv` audit log** so the support manager has a real artifact to grep / chart.

Built on **AgentMail + Claude (web search + tool use)**.

## Pick your language

> **Polling vs webhooks.** This template polls AgentMail every 10s — zero infra, runs from your laptop. For production, switch to webhooks (~10 lines of change). See [Beyond the template](#beyond-the-template).

- [**Python**](./python) — `pip install` and `python agent.py`
- [**TypeScript**](./typescript) — `npm install` and `npm start`

Both versions are functionally identical.

## What you'll need

- An AgentMail API key — https://console.agentmail.to
- An Anthropic API key — https://console.anthropic.com
- Python 3.10+ or Node.js 18+
- A few common Q&As to seed `knowledge_base.md` (the starter file has examples you can replace)
- A real escalation address for your human team

## How it works

1. The agent creates a dedicated AgentMail inbox.
2. Customers email it (or you forward from a `support@` alias).
3. Claude is given four tools:
   - `web_search` — searches `HELP_CENTER_URL` if set
   - `respond(text, classification)` — answer from KB or web search
   - `escalate(reason, classification)` — forward to human team + ack customer
   - `close_ticket(message, classification)` — close when customer signals resolution
4. Every action writes a row to `tickets.csv` for the support manager.
5. Once per polling cycle, the agent checks for tickets escalated >48h ago with no recent follow-up, and sends an unprompted "still working on this" update.

## Customize

- **Knowledge base** — edit `knowledge_base.md`. Use `## Question` headers, write the answer underneath. Loaded into the prompt at startup.
- **System prompt** — `prompt.py` / `prompt.ts`. Tweak tone, classification rules, hard rules.
- **Follow-up cadence** — `FOLLOWUP_AFTER_HOURS` and `FOLLOWUP_COOLDOWN_HOURS` in `.env`.

## Beyond the template

This is the simplest shape that works. For a production deployment:

### Upgrade to webhooks

```python
client.webhooks.create(
    url="https://your-domain.com/agentmail-webhook",
    event_types=["message.received"],
)

@app.post("/agentmail-webhook")
async def webhook(request: Request):
    payload = await request.json()
    if payload["event_type"] == "message.received":
        process_message(payload["message"], inbox)
    return {"ok": True}
```

### Other ideas

- **CRM sync** — POST escalations to Linear / Zendesk / Help Scout when you escalate.
- **VIP routing** — `vip_customers.json` allowlist; auto-escalate VIPs regardless of content.
- **Sentiment dashboard** — pipe `tickets.csv` into a daily Slack digest grouped by classification.
- **Office hours** — different ack messages outside business hours.

## License

MIT
