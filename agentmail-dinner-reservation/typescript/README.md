# Dinner Reservation Agent — TypeScript

A concierge agent that emails restaurants on your behalf, watches for their replies, and confirms your booking with a calendar invite. Built on [AgentMail](https://agentmail.to) + Claude.

> **Polling vs webhooks.** This template polls AgentMail every 15s — zero infra, runs from your laptop. For production, switch to webhooks.

## Setup (3 minutes)

1. **Install**
   ```bash
   npm install
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in `AGENTMAIL_API_KEY`, `ANTHROPIC_API_KEY`, `USER_NAME`, `USER_EMAIL`, and your `TIMEZONE`. The agent only accepts requests from `USER_EMAIL`.

3. **Run**
   ```bash
   npm start
   ```
   On first run the agent creates a fresh AgentMail inbox and prints the address.

4. **Email it a request**
   ```
   To: <agent inbox address>
   Subject: Friday dinner

   Hey, can you book La Brasserie for Friday May 1 at 7pm? Party of 4. Their
   reservations email is reservations@labrasserie.com.
   ```

## How it works

The novel piece: **two-conversation orchestration**. The agent is simultaneously in a thread with you and a thread with the restaurant, and routes messages between them.

For each new email, Claude calls one of five tools:

| Tool | When |
| --- | --- |
| `email_restaurant` | User request has all details |
| `ask_user` | Request is ambiguous |
| `confirm_to_user` | Restaurant confirmed → reply with `CONFIRMED ✓` summary + .ics calendar invite attachment |
| `forward_alternative_to_user` | Restaurant offered different time |
| `tell_user_decline` | Restaurant declined |

Active reservations are tracked in `reservations.json`. The `restaurant_thread_id` on each record is how restaurant replies route back to the correct user thread.

## Files

| File | What it does |
| --- | --- |
| `src/agent.ts` | Polling loop + sender classification + tool dispatch + thread routing. |
| `src/prompt.ts` | System prompt explaining the dual-conversation role + tool reference. |
| `src/reservations.ts` | JSON-backed state for active reservations. |
| `src/calendarInvite.ts` | .ics builder used when confirming a booking. |
| `.env.example` | Copy to `.env` and fill in. |

## Beyond this template

- **Webhooks** for production
- **Auto-retry timeout** — scan for `awaiting_restaurant` records older than 4h, fall back to next restaurant
- **Restaurant lookup** — when user says "find me somewhere good", use Claude's web search against Resy / OpenTable
- **Parallel booking** — email 3 restaurants at once, book whichever confirms first
- **Phone fallback** — pair with a voice agent for restaurants that don't take email reservations
