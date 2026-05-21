# Personal Note Taker — Python

Forward emails to your dedicated inbox, they become Markdown notes with extracted action items. Email questions, the agent searches your notes and replies. Built on [AgentMail](https://agentmail.to) + Claude.

## Setup (3 minutes)

1. **Install**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in API keys, `USER_NAME`, `USER_EMAIL`, optionally `PREFERRED_TAGS`.

3. **Run**
   ```bash
   python agent.py
   ```

The agent prints its inbox address on startup. Forward an email there to capture, or send a question to search.

## How it works

For each unread email, Claude calls one of these tools:

| Tool | When |
| --- | --- |
| `extract_note(summary, tags, action_items, decisions, ...)` | Email looks like content to capture (forward / paste / direct send) |
| `search_notes(query)` | Email body is a question over past notes |
| `discard(reason)` | Newsletter / auto-gen / promotional |

Then **deterministic processing**:

| Classification | What happens |
| --- | --- |
| `extract_note` | Save `notes/<YYYY-MM-DD>-<slug>.md` with YAML frontmatter; append action items to `actions.csv`; reply with summary + path |
| `search_notes` | Run filesystem keyword search; second Claude call composes the answer using the matches; reply with the composed answer |
| `discard` | Mark read with `discarded` label, no reply |

**Special cases:**
- Reply `done` to a note's reply thread → all that note's action items get marked complete in `actions.csv`.
- Same thread re-forwarded → updates existing note (dedup via `thread_id`).
- Agent's own replies (when received back as inbound) are skipped.

**Scheduled jobs (in-loop):**
- Every iteration: check for actions whose deadline is within `REMINDER_HOURS` and fire reminders (deduped via `.notifications.json`).
- Every iteration: if it's `DIGEST_WEEKDAY` past `DIGEST_HOUR`, send the weekly digest (deduped via `.last_digest`).

## Files

| File | What it does |
| --- | --- |
| `agent.py` | Polling loop, classifier call, two-turn search agent, "done" handling. |
| `prompt.py` | Classifier system prompt + search-compose system prompt. |
| `notes_store.py` | Markdown read/write with frontmatter, thread-based dedup, keyword search. |
| `actions.py` | `actions.csv` writer + status updates + dedup hash. |
| `scheduler.py` | 24h-before-deadline reminders + Friday weekly digest. |

## Beyond this template

- **Webhooks** for production (sub-minute capture latency)
- **Embeddings-based search** — swap `notes_store.search` for `voyage-3` once you pass ~100 notes
- **Obsidian / Notion sync** — write notes into your existing vault
- **Auto-linking** between related notes
- **Calendar integration** — push deadline-bearing actions into Google Calendar
