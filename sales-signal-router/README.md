# Sales Signal Router

A real-time sales-signal triage agent. Watches a shared inbox for incoming mail, classifies each message into one of four buckets (hot prospect reply, CRM/billing event, watchlist match, noise), fires the right Slack alert, and emails an end-of-day digest to your sales lead. Built on [AgentMail](https://agentmail.to) + Claude + Slack incoming webhooks.

Two implementations live in this repo:

- [`python/`](./python) — Python 3.10+
- [`typescript/`](./typescript) — Node.js 18+ / TypeScript

Both are functionally identical. Pick whichever you prefer.

## What it does

For each incoming email, Claude calls **exactly one** of four classifier tools:

| Tool | When | Slack action |
| --- | --- | --- |
| `hot_reply` | Human reply on a sales thread (positive intent / objection / OOO / unsub) | DM the rep (looked up via `watchlist.json`) |
| `crm_notification` | Stripe / HubSpot / Salesforce-style event (deal closed, paid, churn, MRR) | Tier by deal size (enterprise / mid / smb) → channel webhook |
| `watchlist_match` | Sender domain or keyword on the watchlist | Alert default channel |
| `noise` | Newsletter, internal, marketing, OOO | No Slack — just logs |

Every classification appends a row to `signals.csv` (audit + analytics). Once a day at `DIGEST_HOUR`, the agent rolls today's signals into an EOD summary and sends it to `SALES_LEAD_EMAIL` + posts to Slack.

## Beyond the bare brief

- **Per-rep Slack DMs.** `watchlist.json:deal_owners` maps a domain to a Slack member ID — hot replies wake up the right person, not the channel.
- **Currency-aware deal sizing.** Claude converts EUR/GBP/CAD to USD before the tier classifier runs.
- **Live-editable watchlist.** The agent re-reads `watchlist.json` on every email, so you can add a new domain mid-day without restarting.
- **Audit log.** `signals.csv` is append-only — every classification, with timestamp, sender, summary, and whether Slack fired.
- **Digest dedup.** `.last_digest` state file prevents the EOD digest from firing twice if the agent restarts after the digest hour.

## Beyond this template

- **Webhooks instead of polling** for sub-second alerts on hot replies
- **Slack OAuth app** instead of webhooks if you want per-rep DMs without listing member IDs in a config file
- **CRM connectors** — instead of parsing Stripe/HubSpot notification emails, hook directly into their APIs
- **Reply-then-classify** — for unrecognized senders, the agent could auto-reply asking for context and re-classify on response
- **Snooze / batching** — group low-priority hot replies (objections, OOOs) into a 4-hourly batch instead of pinging immediately
