# Support Agent — TypeScript

A customer support agent that **triages, responds, escalates, follows up, and closes** — using your own knowledge base and (optionally) your help-center docs. Built on [AgentMail](https://agentmail.to) + Claude.

> **Polling vs webhooks.** This template polls AgentMail every 10s — zero infra, runs from your laptop. For production, switch to webhooks (~10 lines of change). See [Beyond this template](#beyond-this-template).

## Setup (3 minutes)

1. **Install dependencies**
   ```bash
   npm install
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
   Open `knowledge_base.md` (in the project root, alongside `package.json`) and replace the starter Q&As with your own.

4. **Run**
   ```bash
   npm start
   ```

## How it works

For each new email, the agent calls exactly one of three tools — and may use `web_search` first if `HELP_CENTER_URL` is set:

| Tool | When | Effect |
| --- | --- | --- |
| `respond(text, classification)` | The KB or help center has the answer | Reply in-thread, label the ticket |
| `escalate(reason, classification)` | Can't answer, or human approval needed | Forward to `ESCALATION_EMAIL` with reason + classification, send ack to customer |
| `close_ticket(message, classification)` | Customer signaled resolution | Send a friendly close, label as `closed` |

Every action also writes a row to `tickets.csv` for the support manager.

## The 48h follow-up loop

Every polling cycle, the agent checks `.agent_state.json` for tickets escalated more than `FOLLOWUP_AFTER_HOURS` ago AND no follow-up sent in the last `FOLLOWUP_COOLDOWN_HOURS`. If both are true, it sends a "still working on this — apologies for the wait" reply, signed.

## Beyond this template

### Switch from polling to webhooks (recommended for production)

```typescript
await client.webhooks.create({
  url: "https://your-domain.com/agentmail-webhook",
  eventTypes: ["message.received"],
});

app.post("/agentmail-webhook", async (req, res) => {
  const payload = req.body;
  if (payload.event_type === "message.received") {
    await processMessage(payload.message, inbox);
  }
  res.json({ ok: true });
});
```

### Other upgrades

- **CRM sync** — POST escalations to Linear / Zendesk / Help Scout when escalating.
- **VIP routing** — `vip_customers.json` allowlist; auto-escalate VIPs.
- **Sentiment dashboard** — pipe `tickets.csv` into a daily Slack digest grouped by classification.
- **Office hours** — different ack messages outside business hours.
