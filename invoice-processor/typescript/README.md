# Invoice Processor — TypeScript

An accounts-payable agent that reads invoice PDFs straight from email, extracts structured fields (Claude PDF vision, no third-party OCR), matches against your open POs, auto-approves what it can, and escalates the rest. Built on [AgentMail](https://agentmail.to) + Claude.

## Setup (3 minutes)

1. **Install**
   ```bash
   npm install
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in API keys, `COMPANY_NAME`, `AP_EMAIL`, and the routing thresholds.

3. **Add your open POs**
   ```bash
   cp purchase_orders.example.csv purchase_orders.csv
   ```
   Edit with your real open POs.

4. **Run**
   ```bash
   npm start
   ```

## How it works

For each unread email, Claude calls one of two tools:

| Tool | When |
| --- | --- |
| `extract_invoice(vendor_name, invoice_number, amount, currency, due_date, po_number, line_items, notes)` | Confidently extracted from the document |
| `cannot_extract(reason)` | Email isn't an invoice OR critical fields missing |

Then **deterministic routing**:

| Condition | Status | Action |
| --- | --- | --- |
| Duplicate `invoice_number` from same vendor | `duplicate` | Reply to vendor, no AP forward, log |
| No matching open PO | `needs_review_no_po` | Reply asks vendor for PO ref, forward to `AP_EMAIL` |
| Matched PO + amount > `AUTO_APPROVE_LIMIT` | `needs_review_over_limit` | Forward to `AP_EMAIL` for review |
| Matched PO + amount ≤ `AUTO_APPROVE_LIMIT` | `auto_approved` | Reply confirming queued for payment |

Urgent (due ≤ `URGENT_DAYS`) invoices get a `[URGENT]` flag in both vendor ack and AP forward.

## Files

| File | What it does |
| --- | --- |
| `src/agent.ts` | Polling loop, attachment fetch, Claude vision call, routing logic, vendor ack, AP forward. |
| `src/prompt.ts` | Extraction system prompt. |
| `src/purchaseOrders.ts` | CSV-backed PO matcher. |
| `src/invoices.ts` | `invoices.json` duplicate tracker + `invoice_log.csv` audit log. |
| `purchase_orders.example.csv` | Schema reference. |

## Beyond this template

- **Webhooks** for production
- **ERP integration** — replace `purchase_orders.csv` with NetSuite / QuickBooks / Xero
- **3-way match** — extend matching to also verify against goods-received notes
- **Auto-payment** — kick off ACH/wire via Stripe / Mercury for auto-approved invoices
- **Per-vendor rules** — trusted vendors get higher auto-approve thresholds
- **Fraud detection** — flag invoices where vendor banking details changed
