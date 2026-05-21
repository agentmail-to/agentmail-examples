# AgentMail Negotiation Agent

> Multi-party email negotiator. Used cars, apartments, vendor contracts — anything that lives in email.

_Part of the [AgentMail templates collection](https://agentmail.to/build/templates) — runnable open-source agents you can clone and ship in minutes._

You define the deal in `deal.json` — what you're buying, must-haves, ideal/max price, list of counterparties — and the agent runs the negotiation. It fans out opening outreach in parallel, extracts structured offers from each reply, summarizes each round to you with a comparison table + recommendation, and waits for your strategy decision before the next round.

Hard rules baked in: **never reveals your name/location/budget to counterparties**, **never auto-accepts** an offer, **always escalates** when someone crosses your ideal price.

Built on **AgentMail + Claude (tool use)**.

## Pick your language

> **Polling vs webhooks.** This template polls AgentMail every 30s — zero infra, runs from your laptop. For production, switch to webhooks (~10 lines of change).

- [**Python**](./python) — `pip install` and `python agent.py`
- [**TypeScript**](./typescript) — `npm install` and `npm start`

Both versions are functionally identical.

## Use cases

The same agent works for any email-driven negotiation:

| Scenario | `what` | `must_haves` | counterparties |
| --- | --- | --- | --- |
| Used car | "2024 Toyota RAV4 XLE Premium AWD" | trim, mileage, color, no accidents | dealers + private sellers |
| Apartment hunting | "2-bedroom, Brooklyn, $3500 max" | square feet, laundry, pets allowed | brokers + landlords |
| B2B vendor | "Email infrastructure for 200-person team" | SAML, audit logs, EU residency | sales contacts at 3-5 vendors |
| Freelance contract | "Marketing site redesign, 6-week timeline" | portfolio shows SaaS work, US-based | shortlisted freelancers/agencies |

Just edit `deal.json`. No code changes between scenarios.

## What you'll need

- An AgentMail API key — https://console.agentmail.to
- An Anthropic API key — https://console.anthropic.com
- Python 3.10+ or Node.js 18+
- Your address as `BUYER_EMAIL` (only you can send strategy replies)
- A `deal.json` describing what you're negotiating

## How it works

For each counterparty reply, Claude tool-dispatches into:

| Tool | When |
| --- | --- |
| `record_offer(price, currency, terms, meets_must_haves, notes)` | Counterparty quoted a price/terms |
| `mark_declined(reason)` | They passed |
| `answer_question(reply_text)` | They need clarification before quoting; we reply scrubbed of buyer details |

Once every counterparty has reached a terminal state (offered / declined / walked), Claude composes a round summary email to the buyer:

```
Round 1 update — 3 counterparties, 2 offers in.

  Dealer A:  $35,500 OTD  ✓ meets must-haves    (offer)
  Dealer B:  $34,800 OTD  ✓ meets must-haves    (offer)
  Dealer C:  declined — RAV4 XLE Premium not in stock

Recommended: counter Dealer B at $33,500, cite that A is at $35,500.
Hold A as backup; let them know we're shopping. Walk away from C.

Reply with your decision: counter / accept / walk.
```

You reply with strategy in plain English ("counter B at $33k, walk A and C"). Claude translates that into structured tool calls and the next round fires.

## Beyond the template

- **Time-boxed rounds** — current agent waits for ALL counterparties to reply before summarizing. Add a `MAX_ROUND_HOURS` timeout to send the summary regardless.
- **Memory of prior deals** — log all past `deal.json`s so the agent learns your style + acceptable trade-offs.
- **Auto-cite competitors** — let the agent decide when to reveal a competing offer instead of requiring you to specify.

## License

MIT
