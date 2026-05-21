# AgentMail Docs Assistant

> Answer support questions from your docs — escalate what you can't.

_Part of the [AgentMail templates collection](https://agentmail.to/build/templates) — runnable open-source agents you can clone and ship in minutes._

A support agent that lives in an [AgentMail](https://agentmail.to) inbox. Forward customer questions to it (or set up a `support@` alias). It searches your docs site using Claude's native web search tool, replies with a cited answer in the same thread, and forwards anything it can't answer to your real support team — with a short acknowledgment to the customer so they're not left hanging.

Built on **AgentMail + Claude (web search + tool use)**.

## Pick your language

> **Polling vs webhooks.** This template polls AgentMail every 10s — zero infra, runs from your laptop. For production, switch to webhooks (~10 lines of change). See [Beyond the template](#beyond-the-template).

- [**Python**](./python) — `pip install` and `python agent.py`
- [**TypeScript**](./typescript) — `npm install` and `npm start`

Both versions are functionally identical.

## What you'll need

- An AgentMail API key — https://console.agentmail.to
- An Anthropic API key — https://console.anthropic.com
- Python 3.10+ or Node.js 18+
- A docs site to answer from (any public URL — `docs.yourcompany.com`, a Notion site, a Mintlify deployment, etc.)
- A support email address to escalate to

## How it works

1. The agent creates a dedicated AgentMail inbox and prints its address.
2. Customers email that address (or you set up a forwarding alias from your real support inbox).
3. For each question, Claude is given two tools:
   - **`web_search`** — Anthropic's native web search, scoped to your `DOCS_URL` domain only. Returns cited URLs and quoted text.
   - **`escalate(reason)`** — used when the docs don't cover the question. The original email is forwarded to your `ESCALATION_EMAIL` with a one-line note explaining what was searched.
4. The agent replies in-thread with the answer + a "📖 Sources:" footer listing the docs URLs it grounded the answer in. Or, if escalating, sends a short acknowledgment so the customer knows someone's looking.

## Customize

- The **system prompt** lives in `prompt.py` / `prompt.ts`. Edit to change citation style, tone, or escalation rules.
- The **search domain** is `DOCS_URL` in `.env`. Add multiple domains by editing `WEB_SEARCH_TOOL.allowed_domains` directly.

## Beyond the template

This template uses polling + Anthropic's web search because it works the moment you `python agent.py` — no public URL, no docs preprocessing, no vector DB. The two upgrade paths when you outgrow that:

### Upgrade to webhooks (recommended for production)

```python
# 1. Subscribe (run once)
client.webhooks.create(
    url="https://your-domain.com/agentmail-webhook",
    event_types=["message.received"],
)

# 2. Receive (FastAPI / Express / whatever)
@app.post("/agentmail-webhook")
async def webhook(request: Request):
    payload = await request.json()
    if payload["event_type"] == "message.received":
        process_message(payload["message"], inbox)
    return {"ok": True}
```

### Index your docs locally for sub-second answers

Anthropic's web search adds ~2-5s per query. For high-volume support, scrape your docs once into a local vector index (Chroma, LanceDB, etc.) and replace the `web_search` tool with a custom `search_docs(query)` tool that hits your index. Trades setup for speed + cost.

### Other ideas

- **FAQ pre-match** — keep a `faqs.json` of common Q&As, match against the incoming email first, only fall back to web search for novel questions.
- **Multiple docs sources** — main docs + API reference + blog + changelog all in `allowed_domains`.
- **Track satisfaction** — add "👍 helpful? reply YES/NO" and pipe replies into a spreadsheet to surface docs gaps.

## License

MIT
