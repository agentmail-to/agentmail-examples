# Approval Inbox

> **Your inbox is your approval queue. Configure once, approve everything from email.**

A general-purpose human-in-the-loop agent: it watches your inbox for emails matching configured "request types" (vendor invoices, expense reports, refund requests, code reviews, hiring decisions — anything you want to sign off on), extracts the structured fields, and emails you a clean review with a one-line approve/decline prompt. Reply with one word, the agent fires the configured side-effect (forward, webhook, or templated reply), and the loop closes. Built on [AgentMail](https://agentmail.to) + Claude.

Two implementations live in this repo:

- [`python/`](./python) — Python 3.10+
- [`typescript/`](./typescript) — Node.js 18+ / TypeScript

## What it does

For each incoming email, the agent does ONE of the following:

| Case | Action |
| --- | --- |
| Reply on a thread that has a pending request | Parse decision (approve / decline / defer / edit) → update `requests.csv` → fire the configured side-effect actions → ack |
| New email matching a configured type | Claude calls `extract_request(type, fields, summary)` → save to `requests.csv` → email user a clean review with one-line decision prompt |
| New email not matching any type | Claude calls `discard(reason)` → silently mark read |

## Configure the types you care about

Edit `approval_types.yaml`:

```yaml
types:
  - type: vendor_invoice
    description: An invoice from a vendor for goods or services.
    classifier_hints:
      senders: [stripe.com, quickbooks.com]
      keywords: [invoice, "amount due"]
    extract_fields: [vendor, amount_usd, due_date, invoice_number]
    approve:
      forward_to: ap@yourcompany.com
    decline:
      reply_to_sender: "Disputing this invoice. Please send a corrected version."

  - type: code_review
    description: GitHub PR notification asking for review.
    classifier_hints:
      senders: [notifications@github.com]
      keywords: ["[PR]", "pull request"]
    extract_fields: [pr_number, title, files_changed, author]
    approve:
      webhook: https://api.github.com/repos/owner/repo/pulls/{pr_number}/reviews
    decline:
      webhook: https://api.github.com/repos/owner/repo/pulls/{pr_number}/reviews
```

Each `type` defines:
- **classifier_hints** — sender domains / keywords that suggest this type (advisory; Claude still reads the body)
- **extract_fields** — keys the agent extracts from the email and includes in your review
- **approve** / **decline** — side-effect actions to fire on user decision

Side-effect actions supported (any combination):
- `forward_to: <email>` — forward the original to that address
- `webhook: <url>` — POST the request JSON
- `reply_to_sender: <template>` — reply on the original sender's thread (supports `{field_name}` interpolation)

The agent re-reads the YAML on every iteration, so you can add/edit types without restarting.

## Beyond the bare brief

The original "Bills Agent" brief was scoped narrowly to bill payments — but it was just one instance of a much more useful pattern: **email as a bidirectional control surface for any structured approval workflow.** This template generalizes that:

- **Type-driven, not domain-driven** — one agent handles vendor invoices, expense reports, refund requests, code reviews, hiring decisions, GDPR deletion approvals — all from the same `requests.csv` ledger.
- **Decision parser** that understands `approve`, `decline`, `decline: <reason>`, `defer 7d`, `edit: <changes>`, and ✅ / ❌ emoji.
- **Three side-effect primitives** (forward / webhook / templated reply) cover most workflows. Webhook lets it kick off any external system.
- **Field interpolation in reply templates** — `"Refund of {amount_usd} {currency} approved. Ref: {order_id}"` lets the agent compose customer-facing replies from extracted data.
- **Audit-grade ledger** — every classification, every decision, every side-effect captured in `requests.csv` with timestamps + decided_text.
- **Live-editable config** — add a new type to `approval_types.yaml` and the agent picks it up on the next poll, no restart.

## Beyond this template

- **Webhooks** for production (sub-minute extraction)
- **Multi-step approvals** — chain types so e.g. expense-report-over-$500 needs both manager + finance sign-off
- **Slack-mirror** — also DM the user when a request is queued (in addition to email)
- **Auto-approve rules** — for trusted senders + low-amount, skip the user and auto-approve
- **Per-user dispatch** — route different types to different reviewers (e.g. invoices → CFO, code reviews → tech lead)
- **Approval expiry** — pending requests auto-defer after N days if no reply
