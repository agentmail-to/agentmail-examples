# AgentMail Newsletter Digest

> Daily digest from your inbox — newsletters in, ranked top 5-8 out.

_Part of the [AgentMail templates collection](https://agentmail.to/build/templates) — runnable open-source agents you can clone and ship in minutes._

A digest agent that lives in an [AgentMail](https://agentmail.to) inbox. Forward your newsletters there. The agent summarizes each one as it arrives, then once a day at `DIGEST_TIME` it ranks them against your stated interests, dedupes overlapping stories, and emails you the top 5-8 — with links back to original sources.

Built on **AgentMail + Claude (tool use)**.

## Pick your language

> **Polling vs webhooks.** This template polls AgentMail every 30s — zero infra, runs from your laptop. For production, switch to webhooks (~10 lines of change). See [Beyond the template](#beyond-the-template).

- [**Python**](./python) — `pip install` and `python agent.py`
- [**TypeScript**](./typescript) — `npm install` and `npm start`

Both versions are functionally identical.

## What you'll need

- An AgentMail API key — https://console.agentmail.to
- An Anthropic API key — https://console.anthropic.com
- Python 3.10+ or Node.js 18+
- A few real interests to put in `USER_INTERESTS` — the ranking quality depends on this being specific

## How it works

1. The agent creates a dedicated AgentMail inbox.
2. You forward your newsletters to it (or set up auto-forward filters in your real inbox).
3. **Per-email pass**: For each new email, Claude calls one of two tools — `save_summary(headline, key_points, link, topic, importance)` if it's a newsletter, or `skip(reason)` for transactional / personal / cold-outreach mail.
4. **Cache**: Summaries land in `newsletter_cache.json` with 14-day retention.
5. **Daily digest**: At `DIGEST_TIME`, Claude pulls the last 24 hours of items, dedupes overlapping stories, ranks by `USER_INTERESTS`, and calls `compose_digest(subject, body)` with the top 5-8 — which gets emailed to `USER_EMAIL`. If no items, it skips.

## Customize

- **Tone + format** — `prompt.py` / `prompt.ts`. The digest template (greeting, item layout, signoff) lives there.
- **Importance rubric** — what counts as 1/2/3 importance is in the SUMMARIZE prompt.
- **Skip rules** — add your own to the SUMMARIZE prompt (e.g. "skip everything from substack.com").

## Beyond the template

### Upgrade to webhooks

```python
client.webhooks.create(
    url="https://your-domain.com/agentmail-webhook",
    event_types=["message.received"],
)
```

### Other ideas

- **Personal RSS feed** — generate an RSS file from `newsletter_cache.json` so you can read in your feed reader.
- **Per-newsletter rules** — `newsletters.json` allowlist with custom importance modifiers ("always boost Stratechery by +1").
- **Weekly mode** — fork the digest builder to run on Sundays with the past-7-days items.
- **Topic clustering** — for high volume, embed each item with `text-embedding-3-small` and cluster pre-LLM to keep the digest call cheap.

## License

MIT
