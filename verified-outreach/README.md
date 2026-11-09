# AgentMail Verified Outreach

> Verify every prospect before the agent sends. Skip bad addresses, hold risky ones for review, log every decision.

A cold-outreach agent that lives in an [AgentMail](https://agentmail.to) inbox and checks each recipient with [MailVeri](https://mailveri.com) before the first touch goes out. Invalid, disposable and full mailboxes are skipped, so they never turn into bounces on a fresh agent inbox. Role accounts (`info@`, `sales@`) and catch-all domains are held for a human to look at, unless you opt in to sending them.

Built on **AgentMail + MailVeri**. No LLM key needed: the email body is a simple template so the example stays focused on the verification gate. Drop the same gate into [GTM Agent](../gtm-agent) or [Cold Email Researcher](../cold-email-researcher) right before their send call.

## Pick your language

- [**Python**](./python) - `pip install` and `python agent.py`
- [**TypeScript**](./typescript) - `npm install` and `npm start`

Both versions are functionally identical.

## What you'll need

- An AgentMail API key - https://console.agentmail.to
- A MailVeri API key - https://app.mailveri.com/api-keys/
- Python 3.10+ or Node.js 18+
- A list of prospects in `prospects.csv`

## How it works

For each queued prospect the agent calls MailVeri's `POST /v1/verify-mail/` and maps the result to a decision:

| MailVeri status | Default decision | Why |
| --- | --- | --- |
| `VALID` | **send** | Mailbox exists and accepts mail |
| `INVALID` | skip | Mailbox doesn't exist or is disabled |
| `DISPOSABLE` | skip | Temporary / throwaway address |
| `FULL_INBOX` | skip | Mailbox is full, the message would bounce |
| `ROLE_ACCOUNT` | review | Shared inbox. Deliverable, but rarely the right person. `SEND_ROLE_ACCOUNTS=true` to send |
| `CATCH_ALL` | review | Domain accepts everything, so the mailbox can't be confirmed. `SEND_CATCH_ALL=true` to send |
| `UNKNOWN` | review | Mail server didn't give a clear answer. Never sent blind |

Sent messages are labelled `outreach` + `mailveri-<status>` in AgentMail (for example `mailveri-catch-all`), so you can later compare reply and bounce rates per status.

Every decision lands in `verify_log.csv`, and `prospects.csv` keeps the status per row so re-runs don't spend credits on addresses that were already checked.

## Hard rules baked in

- Never send to an address that wasn't verified in this run. Network errors and rate limits leave the row queued for the next run.
- Stop the whole run on an auth error or when MailVeri credits run out. Nothing unverified goes out.
- Respect MailVeri's single-verify rate limit (1 request/second) by default.

## Customize

- **Policy** - `decide()` in `mailveri.py` / `src/mailveri.ts`.
- **Message** - `compose()` in `agent.py` / `src/agent.ts`. Swap in an LLM writer from GTM Agent if you want per-prospect copy.
- **Dry run** - `DRY_RUN=true` verifies and logs without sending (verification still uses credits).

## Beyond the template

- **Bulk lists** - for thousands of rows, upload a file to MailVeri's batch endpoint (`POST /v1/verify-mails/`) and poll `GET /v1/get-status/` instead of verifying one by one.
- **Reply handling** - hand `sent` rows to GTM Agent's polling loop for follow-ups and reply classification.
- **MCP** - if your agent uses tool calls, the [MailVeri MCP server](https://github.com/mailveri/mailveri-mcp) exposes the same check as a `mailveri_verify_email` tool.

## License

MIT
