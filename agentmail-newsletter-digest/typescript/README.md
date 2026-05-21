# Newsletter Digest — TypeScript

A daily digest of the newsletters in your inbox, ranked by what you care about. Built on [AgentMail](https://agentmail.to) + Claude.

> **Polling vs webhooks.** This template polls AgentMail every 30s — zero infra, runs from your laptop. For production, switch to webhooks (~10 lines of change).

## Setup (3 minutes)

1. **Install**
   ```bash
   npm install
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in:
   - `AGENTMAIL_API_KEY`, `ANTHROPIC_API_KEY`
   - `USER_NAME`, `USER_EMAIL`
   - **`USER_INTERESTS`** — comma-separated topics. Be specific.
   - `DIGEST_TIME` — 24h, local time. Default `08:00`.

3. **Run**
   ```bash
   npm start
   ```

## How it works

For each new email, Claude calls one of two tools — `save_summary(headline, key_points, link, topic, importance)` if it's a newsletter, or `skip(reason)` for everything else. Summaries land in `newsletter_cache.json`.

Once per day at `DIGEST_TIME`, Claude pulls the last 24 hours of items, dedupes overlapping stories, ranks by `USER_INTERESTS`, and calls `compose_digest(subject, body)` with the top 5-8 — which gets emailed to `USER_EMAIL`. If no items, it skips.

## Files

| File | What it does |
| --- | --- |
| `src/agent.ts` | Polling loop + per-message tool dispatch + scheduled digest. |
| `src/prompt.ts` | Two system prompts: SUMMARIZE (per-email) and DIGEST (once daily). |
| `src/digest.ts` | Builds the daily digest using Claude tool use + sends via AgentMail. |
| `src/newsletterCache.ts` | JSON-backed cache (with 14-day retention). |
| `.env.example` | Copy to `.env` and fill in. |

## Beyond this template

- **Webhooks** for production (`client.webhooks.create`)
- **RSS export** from `newsletter_cache.json` so you can read in your feed reader
- **Per-newsletter rules** — `newsletters.json` allowlist with custom importance modifiers
- **Weekly mode** — fork the digest builder for Sunday-only weekly runs
