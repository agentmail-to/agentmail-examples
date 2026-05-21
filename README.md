# AgentMail Dinner Reservation Agent

> Email your agent the details — it books the table.

_Part of the [AgentMail templates collection](https://agentmail.to/build/templates) — runnable open-source agents you can clone and ship in minutes._

A concierge agent that lives in an [AgentMail](https://agentmail.to) inbox. You email it the details (restaurant, date, time, party size, restaurant's reservations email). It emails the restaurant on your behalf, watches for the reply, and forwards you the confirmation, alternative time, or decline — without you needing to follow up.

The novel piece in this template: **the agent juggles two parallel email conversations** at once — your thread and the restaurant's thread — and routes messages between them.

Built on **AgentMail + Claude (tool use)**.

## Pick your language

> **Polling vs webhooks.** This template polls AgentMail every 15s — zero infra, runs from your laptop. For production, switch to webhooks (~10 lines of change). See [Beyond the template](#beyond-the-template).

- [**Python**](./python) — `pip install` and `python agent.py`
- [**TypeScript**](./typescript) — `npm install` and `npm start`

Both versions are functionally identical.

## What you'll need

- An AgentMail API key — https://console.agentmail.to
- An Anthropic API key — https://console.anthropic.com
- Python 3.10+ or Node.js 18+
- Your own email address (set as `USER_EMAIL` in `.env`) — the agent only accepts requests from this address

## How it works

1. The agent creates a dedicated inbox.
2. You email the inbox a request like *"book La Brasserie for Friday 7pm, party of 4, their email is reservations@labrasserie.com"*.
3. Claude has 5 tools — picks the right one based on what's happening:

| Tool | When |
| --- | --- |
| `email_restaurant` | Your request has all required details |
| `ask_user` | Your request is ambiguous (one specific question back) |
| `confirm_to_user` | Restaurant replied with confirmation |
| `forward_alternative_to_user` | Restaurant offered a different date/time |
| `tell_user_decline` | Restaurant declined / fully booked |

4. Active reservations are tracked in `reservations.json` so restaurant replies route back to the correct user thread.
5. Once confirmed, you get a clean summary in the original thread:

   ```
   CONFIRMED ✓
   Restaurant: La Brasserie
   Date: Friday May 1 at 7:00 PM
   Party: 4 people
   Confirmed by: Marie (reservations)

   They mentioned they'll set up a table near the window. Dress code is smart casual.
   ```

## Customize

- **Tone of restaurant emails** — `prompt.py` / `prompt.ts`. Default is "professional, under 80 words, signs as your assistant."
- **Format of user-confirmation summary** — see `confirm_to_user` handler in `agent.py` / `agent.ts`.

## Beyond the template

### Switch to webhooks (recommended for production)

```python
client.webhooks.create(url=..., event_types=["message.received"])
```

### v2 ideas

- **Auto-retry on timeout** — scan for `awaiting_restaurant` records older than 4 hours, email a fallback restaurant from a config list, notify the user.
- **Restaurant lookup** — when the user says *"find me somewhere good for sushi"* without naming a place, use Claude's `web_search` tool against Resy / OpenTable / Eater to surface 2-3 options.
- **Calendar invite on confirm** — attach an `.ics` to the user-confirmation reply (see the `agentmail-scheduling-agent` template for the helper).
- **Parallel booking** — for hard-to-book places, email 3 restaurants at once and book whichever confirms first.
- **Phone fallback** — pair with a voice agent (Vapi / Bland) for restaurants that don't take email reservations.

## License

MIT
