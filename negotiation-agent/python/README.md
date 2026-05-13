# Negotiation Agent — Python

A multi-party email negotiator. Tell it what you're trying to buy, your price range, your must-haves, and a list of counterparties — it runs the back-and-forth and reports each round to you with a comparison + next-move recommendation. Built on [AgentMail](https://agentmail.to) + Claude.

> Works for any negotiation that lives in email: used cars, apartment hunting, B2B vendor pricing, freelance contracts, classifieds. Not just dealerships.

## Setup (5 minutes)

1. **Install**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in `AGENTMAIL_API_KEY`, `ANTHROPIC_API_KEY`, and `BUYER_EMAIL` (your address — the agent will only accept strategy replies from this email).

3. **Define your deal**
   ```bash
   cp deal.example.json deal.json
   ```
   Open `deal.json` and fill in:
   - `what` — natural-language description of what you're buying
   - `must_haves` — list of hard requirements
   - `ideal_price` — your target (any offer below this triggers an escalation flag in the round summary)
   - `max_price` — your absolute ceiling (the agent never reveals this number to counterparties)
   - `currency`
   - `deal_context` — free-text extra info: trade-ins, financing, deadlines, location constraints
   - `counterparties` — array of `{email, name}` for each party you want to negotiate with

4. **Run**
   ```bash
   python agent.py
   ```
   The agent immediately fans out opening emails to each counterparty.

## How it works

```
                                    ┌─────────────┐
                          replies   │  Counter-   │
                          ┌─────────│  party A    │
                          │         └─────────────┘
                          │         ┌─────────────┐
   ┌─────────────┐  open  │   reply │  Counter-   │
   │             ├────────┼─────────│  party B    │
   │  Agent      │        │         └─────────────┘
   │  inbox      │        │         ┌─────────────┐
   │             ├────────┼─────────│  Counter-   │
   └─────┬───────┘        │   reply │  party C    │
         │                │         └─────────────┘
         │ round summary  │
         │ + recommendation
         ▼                │
   ┌─────────────┐        │
   │   Buyer     │ "counter A at X, walk B"
   │   (you)     ├────────┘  ← your strategy reply
   └─────────────┘
```

For each counterparty reply, Claude calls one of three tools:

| Tool | What |
| --- | --- |
| `record_offer(price, currency, terms_summary, meets_must_haves, notes)` | Counterparty quoted a price/terms. Structured fields land in `deal.json`. |
| `mark_declined(reason)` | They passed / can't fulfill. We stop pursuing. |
| `answer_question(reply_text)` | They need clarification before quoting. We answer in-thread, scrubbed of buyer details. |

Once every counterparty has reached a terminal state (offered / declined / walked), Claude composes a **round summary** to the buyer with:
- A plain-text comparison table
- A recommended action ("counter A at X, hold B as backup, walk C")
- A `target_hit_alert` flag if any offer crossed `ideal_price`
- A clear CTA: reply with your decision

You reply with strategy in plain English. Claude translates that into one of:

| Tool | Effect |
| --- | --- |
| `next_round(counters[])` | Sends counter emails to specific counterparties at the prices you anchored |
| `walk_away_from(emails[])` | Sends polite close-out emails |
| `escalate_for_human(email, summary)` | You want to accept — agent acknowledges and hands it back to you (never auto-accepts) |

## Hard rules baked in

- **Never reveal** buyer's name / location / max_price / ideal_price to counterparties. Enforced via the writer prompt's redacted-deal context.
- **Never auto-accept.** The agent has no `close_deal` tool. When you say "accept," the response is "deal is in your hands now — reach out directly to finalize."
- **Always escalate** when an offer crosses `ideal_price`. The round summary's subject line gets a `[TARGET HIT]` prefix.
- **Don't leak competitor offers** unless the buyer explicitly tells the agent to cite one as part of a counter (via the `context_for_writer` field).

## Use cases

The same template works for:

- **Used cars** — your N dealers / private sellers, must-haves on trim/mileage, ideal/max price
- **Apartment hunting** — N landlords or brokers, must-haves on bedrooms/laundry/pets, ideal/max rent
- **B2B vendor negotiation** — N SaaS vendors, must-haves on seats/SLAs/integrations, ideal/max contract value
- **Freelance contracts** — N freelancers or agencies, must-haves on scope/timeline, ideal/max budget

Just edit `deal.json`. The prompts are generic enough that no code changes are needed across these scenarios.

## Files

| File | What it does |
| --- | --- |
| `agent.py` | Polling loop + tool dispatch + round-summary scheduler. |
| `prompt.py` | Three system prompts (writer, reply classifier, round summarizer). |
| `deal.py` | JSON-backed deal + counterparty state. |
| `deal.example.json` | Schema reference + sample (used-car negotiation). |
| `.env.example` | Copy to `.env`. |

## Beyond this template

- **Multi-deal support** — currently one deal at a time per inbox. For a portfolio of negotiations, run multiple agents (one per deal) or extend `deal.py` to a list-of-deals schema.
- **Time-boxed rounds** — currently waits for ALL counterparties to reply before sending the round summary. Add a timeout to send the summary after `MAX_ROUND_HOURS` even if some are silent.
- **Auto-cite competitors** — current template requires the buyer to explicitly tell the agent to cite a competitor offer. You could let Claude auto-decide based on a "reveal_competitor" flag.
- **Memory of prior negotiations** — log all past `deal.json`s so the agent learns the buyer's style + acceptable trade-offs over time.
