# Personal Note Taker — TypeScript

Forward emails to your dedicated inbox, they become Markdown notes with extracted action items. Email questions, the agent searches your notes and replies. Built on [AgentMail](https://agentmail.to) + Claude.

## Setup (3 minutes)

1. **Install**
   ```bash
   npm install
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in API keys, `USER_NAME`, `USER_EMAIL`, optionally `PREFERRED_TAGS`.

3. **Run**
   ```bash
   npm start
   ```

The agent prints its inbox address on startup. Forward an email there to capture, or send a question to search.

## How it works

For each unread email, Claude calls one of three tools:

| Tool | When |
| --- | --- |
| `extract_note(...)` | Email is content to capture |
| `search_notes(query)` | Email body is a question over past notes |
| `discard(reason)` | Newsletter / auto-gen / promotional |

Then deterministic processing:

| Classification | What happens |
| --- | --- |
| `extract_note` | Save `notes/<YYYY-MM-DD>-<slug>.md` with YAML frontmatter; append action items to `actions.csv`; reply with summary + path |
| `search_notes` | Filesystem keyword search → second Claude call composes the answer; reply |
| `discard` | Mark read with `discarded` label, no reply |

**Special cases:**
- Reply `done` to a note's reply thread → all actions for that note get marked complete in `actions.csv`.
- Same thread re-forwarded → updates existing note (dedup via `thread_id`).
- Agent's own outbound replies are skipped if they come back inbound.

**Scheduled jobs (in-loop):**
- Reminders fire for actions whose deadline is within `REMINDER_HOURS`.
- Friday weekly digest at `DIGEST_HOUR` (defaults to 17:00).

## Files

| File | What it does |
| --- | --- |
| `src/agent.ts` | Polling loop, classifier call, two-turn search, "done" handling. |
| `src/prompt.ts` | Classifier + search-compose system prompts. |
| `src/notesStore.ts` | Markdown read/write with frontmatter, thread-based dedup, keyword search. |
| `src/actions.ts` | `actions.csv` writer + status updates + dedup hash. |
| `src/scheduler.ts` | 24h reminders + Friday weekly digest. |

## Beyond this template

- **Webhooks** for production (sub-minute capture latency)
- **Embeddings-based search** — swap the keyword search once you pass ~100 notes
- **Obsidian / Notion sync** — write notes into your existing vault
- **Auto-linking** between related notes
- **Calendar integration** — push deadline-bearing actions into Google Calendar
