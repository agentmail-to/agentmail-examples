# Approval Inbox — Python

Configure request types in `approval_types.yaml`. The agent extracts matching emails into structured requests, emails you a clean review, and fires configured side-effects on your one-word reply. Built on [AgentMail](https://agentmail.to) + Claude.

## Setup (3 minutes)

1. **Install**
   ```bash
   pip install -r requirements.txt
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
   python agent.py
   ```

## How it works

Every iteration the agent does TWO things:

**A. Process unread mail.** Per email:

| Case | Action |
| --- | --- |
| Reply on a thread that has a pending request | Parse decision → update `requests.csv` → fire side-effect actions → ack |
| New email | Claude calls `extract_request(type, fields, summary)` OR `discard(reason)` |

**B. Reload the config.** `approval_types.yaml` is re-read every poll so live edits take effect.

### Decision parser

Replies are matched against:

| Reply | Decision |
| --- | --- |
| `approve` / `yes` / `ship` / `ok` / `lgtm` / `✅` / `👍` | `approve` |
| `decline` / `no` / `reject` / `❌` | `decline` |
| `decline: <reason>` | `decline` (with reason captured) |
| `defer 7d` / `snooze 3 days` / `wait 1 week` | `defer` |
| `edit: <text>` / `revise: <text>` | `changes` |

### Side-effect actions

Each type config can specify any combination of:

| Action | Behavior |
| --- | --- |
| `forward_to: <email>` | Forward the original email to that address |
| `webhook: <url>` | POST the request JSON to that URL |
| `reply_to_sender: <template>` | Reply on the original sender's thread (supports `{field_name}` interpolation) |

## Files

| File | What it does |
| --- | --- |
| `agent.py` | Polling loop, classifier call, decision-reply detection. |
| `prompt.py` | Builds the classifier prompt with the configured types. |
| `types_config.py` | Loads `approval_types.yaml` (live re-read). |
| `requests_store.py` | `requests.csv` writer + status updates + thread lookup. |
| `reply_parser.py` | Parses approve/decline/defer/edit from a reply's first line. |
| `actions.py` | Runs `forward_to` / `webhook` / `reply_to_sender` actions. |
| `approval_types.example.yaml` | Schema reference + 3 sample types. |

## Beyond this template

- **Webhooks** for production (sub-minute extraction)
- **Auto-approve rules** — for trusted senders + low-amount, skip the user
- **Multi-step approvals** — e.g. expense > $500 needs manager AND finance
- **Per-user dispatch** — route invoices → CFO, code reviews → tech lead
- **Approval expiry** — pending auto-defers after N days
