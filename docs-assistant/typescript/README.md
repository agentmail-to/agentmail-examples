# Docs Assistant — TypeScript

A support agent that **answers questions from your docs and escalates what it can't**. Built on [AgentMail](https://agentmail.to) + Claude with native web search.

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
   - `DOCS_URL` — full URL of the docs site to answer from (e.g. `https://docs.agentmail.to`)
   - `PRODUCT_NAME` — for context in the agent's system prompt
   - `ESCALATION_EMAIL` — where to forward questions the agent can't answer

3. **Run**
   ```bash
   npm start
   ```
   On first run the agent creates a fresh AgentMail inbox and prints the address. Send (or forward) questions to that address.

## Files

| File | What it does |
| --- | --- |
| `src/agent.ts` | Polling loop + tool dispatch + citation formatting + escalation forwarding. |
| `src/prompt.ts` | System prompt template. Edit to change tone, citation style, escalation rules. |
| `.env.example` | Copy to `.env` and fill in. |

## How it works

1. The polling loop pulls unread mail every `POLL_INTERVAL_SECONDS`.
2. For each question, the agent fetches the full thread and asks Claude with two tools:
   - **`web_search`** — Anthropic's native web search server tool, constrained to your `DOCS_URL` domain via `allowed_domains`. Citations come back attached to the answer for free.
   - **`escalate(reason)`** — custom tool. When Claude can't find an answer in the docs, our code calls `client.inboxes.messages.forward()` to send the original email to `ESCALATION_EMAIL` with the agent's note as a cover, **and** sends a short acknowledgment back to the requester.
3. Otherwise, the agent replies in-thread with the answer + cited URLs at the bottom.

## Beyond this template

### Switch from polling to webhooks (recommended for production)

```typescript
// 1. Subscribe (run once)
await client.webhooks.create({
  url: "https://your-domain.com/agentmail-webhook",
  eventTypes: ["message.received"],
});

// 2. Receive (Express / Hono / whatever)
app.post("/agentmail-webhook", async (req, res) => {
  const payload = req.body;
  if (payload.event_type === "message.received") {
    await processMessage(payload.message, inbox);
  }
  res.json({ ok: true });
});
```

### Other upgrades

- **Index your docs locally** — for sub-second responses, replace web search with a local vector index built once at startup.
- **Pre-screen FAQs** — keep a small `faqs.json` of common questions, match against incoming email first.
- **Multiple docs sources** — set `allowed_domains` to multiple URLs.
- **Track satisfaction** — add a "👍 was this helpful?" line and pipe replies into a spreadsheet to find docs gaps.
