# Scheduling Agent — TypeScript

A scheduling agent that lives in an [AgentMail](https://agentmail.to) inbox. People email it to book time with you, and Claude handles the back-and-forth based on rules you define.

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
   - `USER_NAME`, `USER_EMAIL`, `TIMEZONE` — your details
   - Scheduling rules (`SALES_DAYS`, `BLOCKED_DAYS`, etc.) to taste

3. **Run**
   ```bash
   npm start
   ```
   On first run the agent creates a fresh AgentMail inbox and prints the address. Send an email to that address to start a conversation. The inbox ID is cached in `.agent_state.json` so subsequent runs reuse the same address.

## Files

| File | What it does |
| --- | --- |
| `src/agent.ts` | The polling loop. Fetches unread mail, sends each thread to Claude, replies in-thread, attaches calendar invites. |
| `src/prompt.ts` | The system prompt template + env-var substitution. Edit this to change agent behavior or rules. |
| `src/calendarInvite.ts` | Builds an iCalendar (.ics) file from scratch — no external dependency. Used to attach calendar invites to confirmation emails. |
| `.env.example` | Copy to `.env` and fill in. |

## How it works

1. `getOrCreateInbox()` either loads a cached inbox from `.agent_state.json` or creates a new one.
2. The polling loop calls `client.inboxes.messages.list({ labels: ["unread"] })` for new mail.
3. For each unread message, it fetches the full thread (`client.inboxes.threads.get()`) and converts it into the Anthropic `messages` shape — alternating `user` / `assistant` based on the sender of each message.
4. Claude is given one tool: `confirm_meeting(title, start_iso, duration_minutes)`. The system prompt tells it to call this tool whenever a slot is confirmed.
5. The reply is sent back via `client.inboxes.messages.reply()` (which handles `In-Reply-To` / `References` headers automatically). If Claude called `confirm_meeting`, an `.ics` file is generated and attached — Gmail / Outlook / Apple Mail surface it as a one-click "Add to calendar" invite. `USER_EMAIL` is CC'd so you see every conversation.
6. The original message is marked as read so the next poll skips it.

## Beyond this template

### Switch from polling to webhooks (recommended for production)

Polling makes the template easy to clone and run, but in production you want AgentMail to push events to you the moment they arrive. Roughly 10 lines of change:

```typescript
// 1. Subscribe (run once)
await client.webhooks.create({
  url: "https://your-domain.com/agentmail-webhook",
  eventTypes: ["message.received"],
});

// 2. Replace the polling loop in agent.ts with a webhook handler
app.post("/agentmail-webhook", async (req, res) => {
  const payload = req.body;
  if (payload.event_type === "message.received") {
    // payload.message is the full Message — no second fetch needed
    await processMessage(payload.message, inbox);
  }
  res.json({ ok: true });
});
```

Use the `secret` returned by `webhooks.create()` to HMAC-verify incoming requests.

### Other upgrades

- **Websocket client** — streams events without needing a public URL (works behind NAT).
- **Real calendar API** — the .ics attachment is universal but doesn't sync your availability. Hook in Google Calendar / Outlook to check free/busy before offering slots.
- **Persist conversation state** — every reply re-fetches the thread. Cache it for high-volume use.
