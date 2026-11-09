# Verified Outreach - Python

Verify each prospect with [MailVeri](https://mailveri.com) before an [AgentMail](https://agentmail.to) inbox sends the first touch. Skips invalid, disposable and full mailboxes, holds role accounts and catch-all domains for review, and logs every decision.

## Setup (5 minutes)

1. **Install**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in:
   - `AGENTMAIL_API_KEY`, `MAILVERI_API_KEY`
   - `SENDER_NAME`, `SENDER_COMPANY` - used in the signoff
   - `SEND_ROLE_ACCOUNTS`, `SEND_CATCH_ALL` - leave `false` to hold those for review

3. **Add prospects**
   ```bash
   cp prospects.example.csv prospects.csv
   ```
   Required columns: `email`, `name`, `company`, `hook`. Leave the rest blank, the agent fills them in.

4. **Run**
   ```bash
   python agent.py
   ```
   Tip: run once with `DRY_RUN=true` to see what would be sent before anything goes out.

## How it works

```
prospects.csv (status=queued)
        |
        v
MailVeri POST /v1/verify-mail/  (1 request/second)
        |
        +-- VALID ---------------------------> AgentMail send  -> status=sent
        +-- INVALID / DISPOSABLE / FULL_INBOX -> status=skipped
        +-- ROLE_ACCOUNT / CATCH_ALL / UNKNOWN -> status=needs_review
        |                                       (or send, if you opted in)
        v
verify_log.csv  (one row per decision)
```

To send a row you reviewed, set its `status` back to `queued` and run again with the matching opt-in flag.

## Files

| File | What it does |
| --- | --- |
| `agent.py` | Reads the queue, verifies, decides, sends, logs. |
| `mailveri.py` | Minimal MailVeri client (`verify`) + send policy (`decide`). |
| `prospects.py` | CSV-backed prospect list + `verify_log.csv` helpers. |
| `prospects.example.csv` | Schema reference + sample rows. |
| `.env.example` | Copy to `.env`. |

## Errors

| Situation | What happens |
| --- | --- |
| Network error / HTTP 429 | Retry once, then leave the row `queued` for the next run |
| HTTP 401 / 403 | Stop the run (check `MAILVERI_API_KEY`) |
| `error: 2` (not enough credits) | Stop the run, remaining rows stay `queued` |
