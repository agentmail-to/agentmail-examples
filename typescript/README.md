# Sales Signal Router — TypeScript

Watches a shared inbox, classifies each incoming email into one of four buckets via Claude tool use, fires Slack alerts, and emails an end-of-day digest. Built on [AgentMail](https://agentmail.to) + Claude.

## Setup (3 minutes)

1. **Install**
   ```bash
   npm install
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in API keys, `SLACK_WEBHOOK_URL`, `COMPANY_NAME`, `SALES_LEAD_EMAIL`, and the deal-size thresholds.

   Get a Slack webhook URL: https://api.slack.com/apps → Create New App → Incoming Webhooks → Add to Workspace → pick a channel → copy the URL.

3. **Configure the watchlist**
   ```bash
   cp watchlist.example.json watchlist.json
   ```
   Edit with your real watchlist domains, keywords, and `deal_owners` (Slack member IDs of the reps who own each domain).

4. **Run**
   ```bash
   npm start
   ```

## How it works

For each unread email, Claude calls one of these tools:

| Tool | When |
| --- | --- |
| `hot_reply(sentiment, summary, deal_owner_hint)` | Human reply on a sales thread with buying intent / objection / unsub / OOO |
| `crm_notification(event_type, deal_size_usd, customer, summary)` | Stripe / HubSpot / Salesforce-style event |
| `watchlist_match(matched_term, why, summary)` | Sender or keyword on the watchlist (and not already crm/hot) |
| `noise(reason)` | Everything else |

Then **deterministic routing**:

| Classification | Slack target |
| --- | --- |
| `hot_reply` | `SLACK_WEBHOOK_HOT` (or default) — DMs rep via watchlist.deal_owners |
| `crm_notification` enterprise | `SLACK_WEBHOOK_ENTERPRISE` (or default) |
| `crm_notification` mid/smb | `SLACK_WEBHOOK_URL` (default) |
| `watchlist_match` | `SLACK_WEBHOOK_URL` (default) |
| `noise` | (no Slack) |

Every classification appends a row to `signals.csv`. Once a day at `DIGEST_HOUR` (local), the agent rolls today's signals into an EOD summary and sends it to `SALES_LEAD_EMAIL` + posts to Slack.

## Files

| File | What it does |
| --- | --- |
| `src/agent.ts` | Polling loop, Claude classifier call, fan-out, digest scheduler. |
| `src/prompt.ts` | Classifier system prompt. |
| `src/watchlist.ts` | Live-reload watchlist + rep DM lookup. |
| `src/signals.ts` | `signals.csv` writer + same-day reader. |
| `src/slack.ts` | Webhook fan-out (4 builders). |
| `src/digest.ts` | EOD digest builder + dedupe state. |
| `watchlist.example.json` | Schema reference. |

## Beyond this template

- **Webhooks** for production
- **Slack OAuth app** instead of webhooks for per-rep DMs without listing member IDs
- **CRM connectors** — hit Stripe/HubSpot APIs directly
- **Snooze / batching** — group low-priority signals into a 4-hourly batch
