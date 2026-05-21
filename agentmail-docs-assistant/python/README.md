# Docs Assistant — Python

A support agent that **answers questions from your docs and escalates what it can't**. Built on [AgentMail](https://agentmail.to) + Claude with native web search.

> **Polling vs webhooks.** This template polls AgentMail every 10s — zero infra, runs from your laptop. For production, switch to webhooks (~10 lines of change). See [Beyond this template](#beyond-this-template).

## Setup (3 minutes)

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in:
   - `AGENTMAIL_API_KEY` — from https://console.agentmail.to
   - `ANTHROPIC_API_KEY` — from https://console.anthropic.com
   - `DOCS_URL` — full URL of the docs site to answer from (e.g. `https://docs.agentmail.to`)
   - `PRODUCT_NAME` — for context in the agent's system prompt
   - `ESCALATION_EMAIL` — where to forward questions the agent can't answer

3. **Run**
   ```bash
   python agent.py
   ```
   On first run the agent creates a fresh AgentMail inbox and prints the address. Send (or forward) questions to that address.

## How it works

1. The polling loop pulls unread mail every `POLL_INTERVAL_SECONDS`.
2. For each question, the agent fetches the full thread and asks Claude with two tools:
   - **`web_search`** — Anthropic's native web search server tool, constrained to your `DOCS_URL` domain via `allowed_domains`. Claude can search up to `MAX_SEARCHES_PER_QUESTION` times per email. Citations (URL + cited text) come back attached to the answer for free.
   - **`escalate(reason)`** — custom tool. When Claude can't find an answer in the docs, it calls this with a one-sentence reason. Our code calls `client.inboxes.messages.forward()` to send the original email to `ESCALATION_EMAIL` with the agent's note as a cover, **and** sends a short acknowledgment back to the requester ("looping in our team").
3. Otherwise, the agent replies in-thread with the answer + cited URLs at the bottom.

## Files

| File | What it does |
| --- | --- |
| `agent.py` | Polling loop + tool dispatch + citation formatting + escalation forwarding. |
| `prompt.py` | System prompt template. Edit to change tone, citation style, escalation rules. |
| `.env.example` | Copy to `.env` and fill in. |

## Beyond this template

### Switch from polling to webhooks (recommended for production)

```python
# 1. Subscribe (run once)
client.webhooks.create(
    url="https://your-domain.com/agentmail-webhook",
    event_types=["message.received"],
)

# 2. Replace the polling loop with a webhook handler
@app.post("/agentmail-webhook")
async def webhook(request: Request):
    payload = await request.json()
    if payload["event_type"] == "message.received":
        process_message(payload["message"], inbox)
    return {"ok": True}
```

Use `webhook.secret` to HMAC-verify incoming requests.

### Other upgrades

- **Index your docs locally** — for very large docs sites or where you want sub-second response, replace web search with a local vector index built once at startup. Adds setup but eliminates per-search latency and cost.
- **Pre-screen FAQs** — keep a small `faqs.json` of common questions and exact answers. Match against incoming email first; only fall back to web search for novel questions.
- **Multiple docs sources** — set `allowed_domains` to multiple URLs (e.g. main docs + API reference + blog). Claude will search across all of them.
- **Track satisfaction** — add a "👍 was this helpful? reply YES or NO" line and pipe replies into a spreadsheet to find docs gaps.
