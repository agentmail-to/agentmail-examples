# Newsletter Digest — Python

A daily digest of the newsletters in your inbox, ranked by what you actually care about. Built on [AgentMail](https://agentmail.to) + Claude.

> **Polling vs webhooks.** This template polls AgentMail every 30s — zero infra, runs from your laptop. For production, switch to webhooks (~10 lines of change). See [Beyond this template](#beyond-this-template).

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
   - `USER_NAME`, `USER_EMAIL` — your details
   - **`USER_INTERESTS`** — comma-separated topics. The agent uses this to rank/dedupe items at digest time. Be specific: *"AI agents, growth-loop experiments, B2B pricing, dev tooling"* beats *"tech news"*.
   - `DIGEST_TIME` — 24h format, local time. Default `08:00`.

3. **Run**
   ```bash
   python agent.py
   ```
   On first run the agent creates a fresh AgentMail inbox and prints the address. **Forward your newsletters there** (or set up filters in your real inbox so newsletters auto-forward to this address).

## How it works

```
                   ┌─────────────────────────────────────┐
                   │       AgentMail inbox               │
                   │  (you forward newsletters here)     │
                   └────────────────┬────────────────────┘
                                    │  poll every 30s
                                    ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  Per-email pass (LLM tool-call):                            │
   │    • save_summary(headline, key_points, link, topic, imp.)  │
   │    • skip(reason) ← non-newsletters                         │
   └────────────────┬────────────────────────────────────────────┘
                    │  append to newsletter_cache.json
                    ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  Daily at DIGEST_TIME:                                      │
   │    1. Pull cached items from last 24h                       │
   │    2. Claude dedupes + ranks by USER_INTERESTS              │
   │    3. compose_digest(subject, body) ← top 5-8 items         │
   │    4. Email body sent to USER_EMAIL                         │
   │    5. Sent items removed from cache                         │
   └─────────────────────────────────────────────────────────────┘
```

## Files

| File | What it does |
| --- | --- |
| `agent.py` | Polling loop + per-message tool dispatch + scheduled digest. |
| `prompt.py` | Two system prompts: `summarize` (per-email) and `digest` (once daily). Edit to tune tone/format. |
| `digest.py` | Builds the daily digest using Claude tool use + sends via AgentMail. |
| `newsletter_cache.py` | JSON-backed cache of structured summaries (with 14-day retention). |
| `.env.example` | Copy to `.env` and fill in. |

## Customize

- **Topics & importance** — edit `prompt.py` to change the importance scoring rubric or add custom topic tags.
- **Digest format** — `prompt.py` has the digest template (greeting, item layout, signoff).
- **Skip rules** — the SUMMARIZE prompt lists what counts as "skip". Add your own (e.g. "skip newsletters from ex-employers" or "skip everything from substack.com" if you don't read those).
- **Retention** — `RETENTION_DAYS` in `newsletter_cache.py` (default 14).

## Beyond this template

### Switch from polling to webhooks (recommended for production)

```python
client.webhooks.create(
    url="https://your-domain.com/agentmail-webhook",
    event_types=["message.received"],
)

@app.post("/agentmail-webhook")
async def webhook(request: Request):
    payload = await request.json()
    if payload["event_type"] == "message.received":
        process_message(payload["message"], inbox)
    return {"ok": True}
```

### Other upgrades

- **Topic clustering** — currently the digest dedupes by Claude's judgment. For higher volume, embed each item and cluster pre-LLM to keep the digest call cheap.
- **Personal feed** — generate an RSS file from `newsletter_cache.json` so you can read in your feed reader instead of email.
- **Per-newsletter rules** — keep a `newsletters.json` allowlist with custom importance modifiers (e.g. always boost items from "Stratechery" by +1).
- **Weekly + daily mode** — fork the digest builder to run weekly on Sundays with the past-7-days items if you prefer that cadence.
