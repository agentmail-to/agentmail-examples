# AgentMail GTM Agent

> Personalized multi-touch outreach, reply classification, automatic handoffs.

_Part of the [AgentMail templates collection](https://agentmail.to/build/templates) — runnable open-source agents you can clone and ship in minutes._

A cold-outreach agent that lives in an [AgentMail](https://agentmail.to) inbox. You add prospects to a CSV; the agent personalizes each first-touch using a per-prospect hook, schedules a single follow-up after 4 days if there's no reply, classifies inbound replies (interested / not_interested / ooo / question), and forwards warm leads to your sales team with handoff context.

Built on **AgentMail + Claude (tool use)**.

## Pick your language

> **Polling vs webhooks.** This template polls AgentMail every 30s — zero infra, runs from your laptop. For production, switch to webhooks (~10 lines of change).

- [**Python**](./python) — `pip install` and `python agent.py`
- [**TypeScript**](./typescript) — `npm install` and `npm start`

Both versions are functionally identical.

## What you'll need

- An AgentMail API key — https://console.agentmail.to
- An Anthropic API key — https://console.anthropic.com
- Python 3.10+ or Node.js 18+
- A list of prospects with **specific** hooks (the more concrete the hook, the better the personalization)
- A sales-team email address for warm handoffs

## How it works

For each new email arriving in the inbox, the agent classifies it as a reply to one of its prospects (matched by `thread_id`) and Claude calls one of four tools:

| Tool | When | Effect |
| --- | --- | --- |
| `mark_interested` | Any positive signal (yes / let's talk / send more / curious about pricing) | Forward to `SALES_EMAIL` with cover note + suggested next step |
| `mark_not_interested` | Decline ("not interested", "remove me", "we use X") | Stop touching this prospect, mark `closed_lost` |
| `mark_ooo` | Auto-reply / vacation message | Pause prospect, no follow-up |
| `mark_question` | Clarifying question without taking a side | Reply in-thread with suggested answer |

Plus a scheduled job that, once per polling cycle, sends a single follow-up to any prospect whose first-touch was sent more than `FOLLOWUP_AFTER_HOURS` ago with no reply.

Every action lands in `gtm_log.csv` for the SDR manager to grep / chart.

## Hard rules baked in

- Max two touches per prospect. Then we stop.
- Never follow up after a decline.
- Never reply to declines.

## Customize

- **Hook quality drives email quality** — edit `prospects.csv` with specific signals, not generic compliments.
- **Tone** — `prompt.py` / `prompt.ts`. The default voice is concise, no corporate-speak, one specific ask.
- **Cadence** — `FOLLOWUP_AFTER_HOURS` in `.env`.

## Beyond the template

- **Multi-touch sequences** — extend follow-up to a list (day 4, 11, 25).
- **Enrichment** — auto-fetch hook context from Clearbit / Apollo at first-touch time.
- **A/B testing** — randomize subject patterns, log which converts in `gtm_log.csv`.
- **Reply scoring** — extend classifier with a `qualification_score`, only hand off >= threshold.
- **Send-window** — only send during recipient's business hours.

## License

MIT
