# Inbox Zero Agent — TypeScript

An agent that watches your inbox while you sleep and **drafts replies for you to review in the morning**. Built on [AgentMail](https://agentmail.to) + Claude.

> **Polling vs webhooks.** This template polls AgentMail every 20s — zero infra, runs from your laptop. For production, switch to webhooks (~10 lines of change). See [Beyond this template](#beyond-this-template).

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
   - `USER_NAME`, `USER_EMAIL`, `TIMEZONE`
   - `STYLE_EXAMPLES` — **important** — paste a few paragraphs of your own writing so drafts sound like you. Wrap the multi-line value in double quotes for dotenv to parse it correctly.
   - `WAKE_TIME` — when to send the morning digest (default `08:00`)

3. **Run**
   ```bash
   npm start
   ```
   On first run the agent creates a fresh AgentMail inbox and prints the address. Forward mail there (or set up filters in your real inbox) to start drafting.

## Files

| File | What it does |
| --- | --- |
| `src/agent.ts` | Polling loop + tool dispatch + digest scheduling. |
| `src/prompt.ts` | System prompt template. Edit to change classification rules or drafting style. |
| `src/digest.ts` | Builds the morning digest email body and decides when to send. |
| `.env.example` | Copy to `.env` and fill in. |

## How it works

1. The polling loop pulls unread mail every `POLL_INTERVAL_SECONDS`.
2. For each new email, the agent fetches the full thread and asks Claude to choose exactly one of three tools:
   - `draft_reply(text)` — save a draft via `client.inboxes.drafts.create()` (with `inReplyTo` to preserve threading)
   - `flag_for_human(reason)` — label the message for your attention; no draft
   - `mark_handled(category)` — for spam, promotional, FYI, or automated notifications
3. Each processed email gets a category label and is marked read.
4. At `WAKE_TIME` each day, the agent sends a digest email to `USER_EMAIL` listing every draft created and every email flagged.

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

Use the `secret` returned by `webhooks.create()` to HMAC-verify incoming requests.

### Other upgrades

- **Better style matching** — replace static `STYLE_EXAMPLES` with your actual sent folder (last 50 messages).
- **Quiet hours** — only act on emails received outside your working hours.
- **One-click send** — wire up a "reply YES to send" flow so you can approve drafts from the digest email itself.
- **Per-sender rules** — VIP senders always get drafts, mailing lists always get marked-handled.
