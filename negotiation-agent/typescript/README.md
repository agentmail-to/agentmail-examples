# Negotiation Agent — TypeScript

A multi-party email negotiator. Tell it what you're trying to buy, your price range, must-haves, and a list of counterparties — it runs the back-and-forth and reports each round to you with a comparison + next-move recommendation. Built on [AgentMail](https://agentmail.to) + Claude.

> Works for any negotiation that lives in email: used cars, apartment hunting, B2B vendor pricing, freelance contracts, classifieds. Not just dealerships.

## Setup (5 minutes)

1. **Install**
   ```bash
   npm install
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in API keys and `BUYER_EMAIL` (your address).

3. **Define your deal**
   ```bash
   cp deal.example.json deal.json
   ```
   Open `deal.json` and fill in `what`, `must_haves`, `ideal_price`, `max_price`, `currency`, `deal_context`, and the `counterparties` array.

4. **Run**
   ```bash
   npm start
   ```

## How it works

For each counterparty reply, Claude calls one of three tools:

| Tool | When |
| --- | --- |
| `record_offer(price, currency, terms_summary, meets_must_haves, notes)` | Counterparty quoted a price/terms |
| `mark_declined(reason)` | They passed |
| `answer_question(reply_text)` | They need clarification before quoting |

When all counterparties reach a terminal state, Claude composes a round summary email with comparison table + recommendation. You reply with strategy in plain English, and Claude translates that into:

| Tool | Effect |
| --- | --- |
| `next_round(counters[])` | Sends counter emails to specific counterparties at the prices you anchored |
| `walk_away_from(emails[])` | Sends polite close-out emails |
| `escalate_for_human(email, summary)` | You want to accept — agent acknowledges and hands it back |

## Hard rules baked in

- Never reveal buyer's name / location / max_price / ideal_price to counterparties
- Never auto-accept (no `close_deal` tool exists)
- Always escalate when an offer crosses `ideal_price` — round summary subject gets `[TARGET HIT]`
- Don't leak competitor offers unless the buyer explicitly tells the agent to cite one

## Files

| File | What it does |
| --- | --- |
| `src/agent.ts` | Polling loop + tool dispatch + round-summary scheduler |
| `src/prompt.ts` | Three system prompts (writer, reply classifier, round summarizer) |
| `src/deal.ts` | JSON-backed deal + counterparty state |
| `deal.example.json` | Schema reference + sample (used-car negotiation) |

## Beyond this template

- **Time-boxed rounds** — currently waits for ALL counterparties to reply before summarizing
- **Memory** — log past `deal.json`s so the agent learns your style
- **Auto-cite competitors** — let the agent decide when to reveal a competing offer
