# Sales Signal Router — Python

Watches a shared inbox, classifies each incoming email into one of four buckets via Claude tool use, fires Slack alerts, and emails an end-of-day digest. Built on [AgentMail](https://agentmail.to) + Claude.

## Setup (3 minutes)

1. **Install**
   ```bash
   pip install -r requirements.txt
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
   Edit `watchlist.json` with your real watchlist domains, keywords, and `deal_owners` (Slack member IDs of the reps who own each domain).

4. **Run**
   ```bash
   python agent.py
   ```

## How it works

For each unread email, Claude calls one of these tools:

| Tool | When |
| --- | --- |
| `hot_reply(sentiment, summary, deal_owner_hint)` | Human reply on a sales thread with buying intent / objection / unsub / OOO |
| `crm_notification(event_type, deal_size_usd, customer, summary)` | Stripe / HubSpot / Salesforce-style automated event |
| `watchlist_match(matched_term, why, summary)` | Sender or keyword on the watchlist (and not already crm/hot) |
| `noise(reason)` | Everything else |

Then **deterministic routing**:

| Classification | Action | Slack target |
| --- | --- | --- |
| `hot_reply` | DM rep (looked up via `watchlist.deal_owners`) | `SLACK_WEBHOOK_HOT` (or default) |
| `crm_notification` enterprise (≥ `ENTERPRISE_THRESHOLD`) | Channel ping | `SLACK_WEBHOOK_ENTERPRISE` (or default) |
| `crm_notification` mid/smb | Channel ping | `SLACK_WEBHOOK_URL` (default) |
| `watchlist_match` | Channel ping | `SLACK_WEBHOOK_URL` (default) |
| `noise` | (no Slack) | — |

Every classification appends a row to `signals.csv`.

Once a day at `DIGEST_HOUR` (local), the agent rolls today's signals into an EOD digest:
1. Posts to Slack via `SLACK_WEBHOOK_DIGEST` (or default)
2. Emails `SALES_LEAD_EMAIL`

The `.last_digest` file dedupes against re-runs / restarts.

## Files

| File | What it does |
| --- | --- |
| `agent.py` | Polling loop, Claude classifier call, fan-out, digest scheduler. |
| `prompt.py` | Classifier system prompt (the four tools' descriptions). |
| `watchlist.py` | Loads `watchlist.json` on every iteration; finds rep DM ID by sender domain. |
| `signals.py` | `signals.csv` audit log writer + same-day reader for the digest. |
| `slack.py` | Incoming-webhook fan-out (4 builders: hot / crm / watchlist / digest). |
| `digest.py` | EOD digest builder + dedupe state. |
| `watchlist.example.json` | Schema reference. |

## Beyond this template

- **Webhooks** for production (sub-second hot-reply alerts)
- **Slack OAuth app** instead of webhooks for per-rep DMs without listing member IDs
- **CRM connectors** — hit Stripe/HubSpot APIs directly instead of parsing their notification emails
- **Snooze / batching** — group low-priority signals into a 4-hourly batch
