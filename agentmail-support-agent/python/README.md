# Support Agent — Python

A customer support agent that **triages, responds, escalates, follows up, and closes** — using your own knowledge base and (optionally) your help-center docs. Built on [AgentMail](https://agentmail.to) + Claude.

> **Polling vs webhooks.** This template polls AgentMail every 10s — zero infra, runs from your laptop. For production, switch to webhooks (~10 lines of change). See [Beyond this template](#beyond-this-template).

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
   - `PRODUCT_NAME`, `AGENT_NAME` — what the agent represents and signs as
   - `ESCALATION_EMAIL` — where unresolved tickets get forwarded
   - `HELP_CENTER_URL` — optional, Claude will search this too via web_search

3. **Edit your knowledge base**
   Open `knowledge_base.md` and replace the starter Q&As with your own. The agent loads this whole file into the system prompt at startup, so keep it ~30-50 entries (longer is fine but the prompt gets noisy).

4. **Run**
   ```bash
   python agent.py
   ```
   On first run the agent creates a fresh AgentMail inbox and prints the address. Forward customer emails to it (or set up a `support@` alias).

## How it works

For each new email, the agent calls exactly one of three tools — and may use `web_search` first if `HELP_CENTER_URL` is set:

| Tool | When | Effect |
| --- | --- | --- |
| `respond(text, classification)` | The KB or help center has the answer | Reply in-thread, label the ticket |
| `escalate(reason, classification)` | Can't answer, or human approval needed (refunds, custom contracts) | Forward to `ESCALATION_EMAIL` with reason + classification, send ack to customer |
| `close_ticket(message, classification)` | Customer signaled resolution ("thanks, that worked") | Send a friendly close, label as `closed` |

Every action also writes a row to `tickets.csv`:

```
timestamp_utc,action,classification,sender,subject,message_id,thread_id,note
2026-04-28T14:32:01+00:00,responded,billing,user@example.com,How do I cancel?,...,...,Log in and go to Settings → Billing...
```

You can grep, sort, or import this into a spreadsheet for ticket dashboards.

## The 48h follow-up loop

Every polling cycle, the agent checks `.agent_state.json` for tickets that were escalated more than `FOLLOWUP_AFTER_HOURS` ago AND haven't received a follow-up in the last `FOLLOWUP_COOLDOWN_HOURS`. If both are true, it sends a "still working on this — apologies for the wait" reply, signed.

This keeps customers from feeling abandoned while the human team is working through the queue.

## Hard rules baked into the prompt

The agent is instructed to:

- **Never commit to refunds, custom pricing, SLA terms, or specific timelines.** These always escalate.
- **Always escalate angry customers**, even if the KB has the answer. Humans handle conflict.
- **Never invent product details.** If the KB and web search both miss, escalate.
- **Always sign as `{AGENT_NAME}, Support Team`** on responses and closes.

Edit `prompt.py` to change any of these.

## Files

| File | What it does |
| --- | --- |
| `agent.py` | Polling loop + tool dispatch + 48h follow-up scheduler. |
| `prompt.py` | System prompt + KB injection. Edit to change tone, classification rules, escalation logic. |
| `knowledge_base.md` | Your common Q&As — **replace the starter content with your own**. |
| `ticket_log.py` | CSV append helper. Schema documented at top of file. |
| `.env.example` | Copy to `.env` and fill in. |

## Beyond this template

### Switch from polling to webhooks (recommended for production)

```python
# 1. Subscribe (run once)
client.webhooks.create(
    url="https://your-domain.com/agentmail-webhook",
    event_types=["message.received"],
)

# 2. Replace the polling loop with a webhook handler
@app.post("/agentmail-webhook")
async def webhook(request: Request):
    payload = await request.json()
    if payload["event_type"] == "message.received":
        process_message(payload["message"], inbox)
    return {"ok": True}
```

### Other upgrades

- **VIP routing** — keep a `vip_customers.json` allowlist; auto-escalate any email from those addresses regardless of content.
- **CRM sync** — when escalating, also POST to your Linear / Zendesk / Help Scout API. The classification field maps cleanly to ticket types.
- **Sentiment dashboard** — pull `tickets.csv` into a daily Slack digest grouped by classification.
- **Office hours** — have the agent send a different acknowledgment ("we'll respond by 9am tomorrow") outside business hours.
- **Auto-close stale escalations** — extend the follow-up loop: after N follow-ups with no customer reply, send a "we'll close this in 7 days" warning.
