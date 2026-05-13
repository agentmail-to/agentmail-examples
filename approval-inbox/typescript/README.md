# Approval Inbox — TypeScript

Configure request types in `approval_types.yaml`. The agent extracts matching emails into structured requests, emails you a clean review, and fires configured side-effects on your one-word reply. Built on [AgentMail](https://agentmail.to) + Claude.

## Setup (3 minutes)

1. **Install**
   ```bash
   npm install
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in API keys, `USER_NAME`, `USER_EMAIL`.

3. **Configure your request types**
   ```bash
   cp approval_types.example.yaml approval_types.yaml
   ```
   Edit it. Each type has classifier hints, fields to extract, and approve/decline actions.

4. **Run**
   ```bash
   npm start
   ```

## How it works

For each incoming email:

| Case | Action |
| --- | --- |
| Reply on a thread with a pending request | Parse decision → update `requests.csv` → fire side-effect actions → ack |
| New email | Claude calls `extract_request(type, fields, summary)` OR `discard(reason)` |

The agent re-reads `approval_types.yaml` every poll, so live edits to the config take effect without restarting.

### Decision parser

| Reply | Decision |
| --- | --- |
| `approve` / `yes` / `ship` / `lgtm` / `✅` | `approve` |
| `decline` / `no` / `reject` / `❌` | `decline` |
| `decline: <reason>` | `decline` (with reason) |
| `defer 7d` / `snooze 3 days` / `wait 1 week` | `defer` |
| `edit: <text>` / `revise: <text>` | `changes` |

### Side-effect actions

| Action | Behavior |
| --- | --- |
| `forward_to: <email>` | Forward original email to that address |
| `webhook: <url>` | POST request JSON to that URL |
| `reply_to_sender: <template>` | Reply on the original sender's thread (with `{field_name}` interpolation) |

## Files

| File | What it does |
| --- | --- |
| `src/agent.ts` | Polling loop, classifier, decision-reply handling. |
| `src/prompt.ts` | Builds the classifier prompt with configured types. |
| `src/typesConfig.ts` | Loads `approval_types.yaml` (live re-read). |
| `src/requestsStore.ts` | `requests.csv` writer + status updates + thread lookup. |
| `src/replyParser.ts` | Parses approve/decline/defer/edit. |
| `src/actions.ts` | Runs `forward_to` / `webhook` / `reply_to_sender`. |

## Beyond this template

- **Webhooks** for production
- **Auto-approve rules** for trusted senders + low amounts
- **Multi-step approvals** (manager + finance)
- **Per-user dispatch** by type
- **Approval expiry** auto-defers after N days
