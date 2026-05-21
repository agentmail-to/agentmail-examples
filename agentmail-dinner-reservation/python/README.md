# Dinner Reservation Agent — Python

A concierge agent that emails restaurants on your behalf, watches for their replies, and confirms your booking — without you needing to follow up. Built on [AgentMail](https://agentmail.to) + Claude.

> **Polling vs webhooks.** This template polls AgentMail every 15s — zero infra, runs from your laptop. For production, switch to webhooks (~10 lines of change). See [Beyond this template](#beyond-this-template).

## Setup (3 minutes)

1. **Install**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in:
   - `AGENTMAIL_API_KEY`, `ANTHROPIC_API_KEY`
   - `USER_NAME`, `USER_EMAIL` — `USER_EMAIL` is the address you'll send reservation requests *from*. The agent only accepts requests from this address.

3. **Run**
   ```bash
   python agent.py
   ```
   On first run the agent creates a fresh AgentMail inbox and prints the address.

4. **Email it a request**
   ```
   To: <agent inbox address>
   Subject: Friday dinner

   Hey, can you book La Brasserie for Friday May 1 at 7pm? Party of 4. Their
   reservations email is reservations@labrasserie.com. We have one vegetarian
   in the group.
   ```
   The agent emails the restaurant, watches for their reply, and forwards you the confirmation/alternative/decline.

## How it works

The novel piece is **two-conversation orchestration**: the agent is simultaneously in a thread with you AND a thread with the restaurant, and routes messages between them.

```
                 ┌────────────────┐
   USER_EMAIL ──▶│                │
                 │  Agent inbox   │──▶ restaurant@example.com
   USER_EMAIL ◀──│                │◀── (restaurant replies)
                 └────────────────┘
                  reservations.json
                  tracks each request:
                   - user_thread_id
                   - restaurant_thread_id
                   - status, details
```

For each new email, the agent classifies the sender:

- **From `USER_EMAIL`** — it's a request (or clarification reply). Claude either calls `email_restaurant` (with structured details extracted from the natural-language request) or `ask_user` (one specific clarifying question).
- **On a thread tied to an active reservation** — it's a restaurant reply. Claude calls `confirm_to_user`, `forward_alternative_to_user`, or `tell_user_decline` based on the reply's content.
- **Anything else** — labeled `unknown_sender` and ignored.

State across reservations lives in `reservations.json`. The `restaurant_thread_id` on each record is how we route a restaurant's reply back to the correct user thread.

## Tools

| Tool | When | Effect |
| --- | --- | --- |
| `email_restaurant` | User request has all details | Sends booking email, opens a new thread, records the reservation |
| `ask_user` | User request is ambiguous | Replies in the user's thread with one question |
| `confirm_to_user` | Restaurant confirmed | Sends `CONFIRMED ✓` summary in the user's original thread |
| `forward_alternative_to_user` | Restaurant offered different time | Forwards alternative + asks user if it works |
| `tell_user_decline` | Restaurant declined or full | Forwards decline + suggests next step |

Edit `prompt.py` to change the agent's tone, when each tool fires, or the user-message format.

## Files

| File | What it does |
| --- | --- |
| `agent.py` | Polling loop + sender classification + tool dispatch + thread routing. |
| `prompt.py` | System prompt explaining the dual-conversation role + tool reference. |
| `reservations.py` | JSON-backed state for active reservations. |
| `.env.example` | Copy to `.env` and fill in. |

## Beyond this template

### Switch to webhooks (recommended for production)

```python
client.webhooks.create(url=..., event_types=["message.received"])
```

### v2 ideas

- **Auto-retry timeout** — the brief mentions "no reply after 4 hours, try the next restaurant." Add a polling pass that scans for `awaiting_restaurant` records older than N hours and emails a fallback restaurant from a config list.
- **Restaurant lookup** — when the user says "find me somewhere good for sushi in SoMa" without naming a place, use Claude's web_search tool against a restaurant guide (Resy / OpenTable / Eater) to suggest 2-3 options, then proceed.
- **Calendar invite** — once confirmed, attach an `.ics` file to the user-confirmation reply (see the `agentmail-scheduling-agent` template for the helper).
- **Multiple parallel options** — for hard-to-book places, email 3 restaurants in parallel and book whichever confirms first.
- **Phone fallback** — for restaurants that don't take email reservations, integrate with a calling agent (Vapi / Bland) and have the dinner agent kick off the call.
