# GTM Agent — TypeScript

A cold-outreach agent that personalizes the first touch, follows up after 4 days, classifies replies, and hands warm leads off to sales — without you babysitting it. Built on [AgentMail](https://agentmail.to) + Claude.

## Setup (5 minutes)

1. **Install**
   ```bash
   npm install
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in API keys, `SENDER_NAME` / `SENDER_ROLE` / `SENDER_COMPANY`, `SALES_EMAIL`.

3. **Add prospects**
   ```bash
   cp prospects.example.csv prospects.csv
   ```
   Replace the rows. Required columns: `email`, `name`, `role`, `company`, `hook`. The hook is the most important field — make it specific.

4. **Run**
   ```bash
   npm start
   ```

## How it works

- **Per-prospect personalization**: Claude generates a fresh email per prospect from the `hook` field. No template body.
- **Reply classification (Claude tool use)** — 4 outcomes:
  - `mark_interested` → sends an immediate warm acknowledgment to the prospect in-thread, then forwards the reply to `SALES_EMAIL` with a handoff cover note + suggested next step
  - `mark_not_interested` → status flips to `closed_lost`, no reply sent
  - `mark_ooo` → pauses follow-up
  - `mark_question` → replies in-thread with a suggested answer
- **4-day single follow-up** automatically. Then we stop. Max 2 touches.
- **Audit log**: `gtm_log.csv` captures every action.

## Hard rules baked in

- Max two touches per prospect
- Never follow up after a decline
- Never reply to declines

## Files

| File | What it does |
| --- | --- |
| `src/agent.ts` | Polling loop, outreach, follow-ups, reply dispatch. |
| `src/prompt.ts` | WRITER (cold-email body) + CLASSIFIER (reply tool dispatch) prompts. |
| `src/prospects.ts` | CSV-backed prospect tracker + audit log. |
| `prospects.example.csv` | Schema reference. |

## Beyond this template

- **Multi-touch sequences** — extend follow-up to a list (day 4, 11, 25)
- **Enrichment** — auto-fetch hook context from Clearbit / Apollo at first-touch time
- **A/B subject lines** — log which converts in `gtm_log.csv`
- **Reply scoring** — extend classifier with a qualification score, only hand off >= threshold
- **Send-window** — only send during recipient's business hours
