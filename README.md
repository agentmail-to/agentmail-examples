# Personal Note Taker

A personal knowledge-base agent that lives in your inbox. Forward an email (or send one directly), it becomes a structured Markdown note with extracted action items, decisions, and open questions. Email a question, it searches your past notes and replies with the answer. Built on [AgentMail](https://agentmail.to) + Claude.

Two implementations live in this repo:

- [`python/`](./python) — Python 3.10+
- [`typescript/`](./typescript) — Node.js 18+ / TypeScript

Both are functionally identical. Pick whichever you prefer.

## What it does

For each incoming email, Claude calls **exactly one** of three classifier tools:

| Tool | When | Action |
| --- | --- | --- |
| `extract_note` | Forward / paste / direct send — content to remember | Save Markdown note in `notes/<date>-<slug>.md` with YAML frontmatter (tags, source, thread_id). Append action items to `actions.csv`. Reply with summary + permalink. |
| `search_notes(query)` | Email is a question over past notes | Two-turn agent: filesystem search → second Claude call composes the answer → reply. |
| `discard(reason)` | Newsletter / auto-gen / promotional | Silently mark read. |

**Closing the loop.** Reply `done` to a note's reply thread → all that note's action items get marked complete in `actions.csv`.

**Reminders & digest.**
- 24 hours before any action's deadline → reminder emailed to you (set `NOTIFY_ASSIGNEES=true` to also email the assignee directly).
- Friday at 17:00 (configurable) → weekly digest of open + overdue actions, grouped by urgency.

## Beyond the bare brief

The original brief had the agent email the structured note back to the user — but that left the notes living only in your inbox, not searchable as a real knowledge base. We fixed that:

- **Notes have a home.** Each note is a Markdown file with YAML frontmatter, on disk under `notes/`. Edit them by hand if you want — the agent re-reads from disk on every search.
- **Knowledge-base search via tool use.** Email `what did Sarah say about Q3?` to the agent and it searches all your past notes (via the `search_notes` tool), then composes an answer in a second Claude turn that cites the matched note paths.
- **Action completion via reply.** Reply `done` to any note's reply thread and the agent marks all that note's action items complete. Closes the loop without leaving your email client.
- **Thread-level dedup.** Forward the same thread twice → updates the existing note instead of creating a duplicate.
- **Assignee notification is opt-in.** The brief said "email each action-item owner directly" — for a template that's risky (your colleagues get unsolicited mail from `notes-agent@agentmail.to`). Default is to surface action items to YOU and let you decide what to forward; flip `NOTIFY_ASSIGNEES=true` if you trust it.

## Beyond this template

- **Webhooks** instead of polling for sub-minute capture
- **Embeddings-based search** (swap the keyword search in `notes_store.search` for `voyage-3` or `text-embedding-3-large`) — pays off past ~100 notes
- **Obsidian / Notion sync** — write notes into your existing vault instead of `notes/`
- **Auto-linking** — when a new note mentions a name/topic that appears in other notes, add a "Related" section
- **Calendar integration** — push action items with deadlines into Google Calendar / Cal.com
