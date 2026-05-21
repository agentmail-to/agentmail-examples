# AgentMail Invoice Processor

> AP agent that reads invoice PDFs from email, extracts fields, matches POs, auto-approves what it can, escalates the rest.

_Part of the [AgentMail templates collection](https://agentmail.to/build/templates) — runnable open-source agents you can clone and ship in minutes._

A finance agent that lives in an [AgentMail](https://agentmail.to) inbox. Vendors email their invoices (PDF or image) to it. The agent uses **Claude's native PDF vision** to extract structured fields (vendor, invoice number, amount, currency, due date, PO number), matches against your open POs, decides whether to auto-approve or escalate based on a configurable threshold, replies to the vendor with the status, and forwards anything that needs human review to your AP team.

No third-party OCR service. No accounting API integration required. Just AgentMail + Claude.

## Pick your language

> **Polling vs webhooks.** This template polls AgentMail every 30s — zero infra, runs from your laptop. For production, switch to webhooks.

- [**Python**](./python) — `pip install` and `python agent.py`
- [**TypeScript**](./typescript) — `npm install` and `npm start`

## What you'll need

- An AgentMail API key — https://console.agentmail.to
- An Anthropic API key — https://console.anthropic.com
- Python 3.10+ or Node.js 18+
- A list of your open purchase orders (in `purchase_orders.csv`)
- Your AP team's email address (for escalations)

## How it works

```
   ┌────────────────┐
   │ Vendor invoice │  forwarded to agent inbox
   │ (PDF / image)  │
   └───────┬────────┘
           ▼
   ┌─────────────────────────────────────────────┐
   │  Claude vision (PDF / image as document)    │
   │    extract_invoice(vendor, inv#, $$, due,   │
   │                    PO, line items, notes)   │
   └───────┬─────────────────────────────────────┘
           ▼
   ┌─────────────────────────┐
   │  Routing rules:         │
   │  • duplicate?           │  →  reply, log, stop
   │  • PO match?            │
   │    └ no  → escalate     │  →  forward to AP_EMAIL
   │    └ yes & ≤ $LIMIT     │  →  auto-approve, queue payment
   │    └ yes & > $LIMIT     │  →  escalate to AP team
   │  • due ≤ URGENT_DAYS?   │  →  ⚠️ URGENT label
   └─────────────────────────┘
           ▼
   ┌──────────────────┐  ┌──────────────────┐
   │ Vendor ack reply │  │  invoice_log.csv │  audit trail
   └──────────────────┘  └──────────────────┘
```

## Hard rules baked in

- Never process without an invoice number
- Never process duplicate invoice numbers from the same vendor
- Never auto-approve without a matching PO
- Always flag urgent (due ≤ `URGENT_DAYS`)

## Beyond the template

- **Real ERP integration** — replace `purchase_orders.csv` with a live query against NetSuite / QuickBooks / SAP / Xero
- **3-way match** — extend to verify against goods-received notes
- **Auto-payment** — kick off ACH/wire via Stripe / Mercury / Modern Treasury for auto-approved invoices
- **Per-vendor rules** — trusted vendors get higher auto-approve thresholds
- **Fraud detection** — flag invoices where vendor banking details changed since last paid invoice

## License

MIT
