# Invoice Processor — Python

An accounts-payable agent that reads invoice PDFs straight from email, extracts structured fields, matches against your open POs, auto-approves what it can, and escalates the rest. Built on [AgentMail](https://agentmail.to) + Claude (native PDF vision, no third-party OCR).

> **Polling vs webhooks.** This template polls AgentMail every 30s — zero infra, runs from your laptop. For production, switch to webhooks.

## Setup (3 minutes)

1. **Install**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in:
   - `AGENTMAIL_API_KEY`, `ANTHROPIC_API_KEY`
   - `COMPANY_NAME` — appears in vendor acknowledgments
   - `AP_EMAIL` — where escalated invoices get forwarded
   - `AUTO_APPROVE_LIMIT` — dollar threshold (default 5000)
   - `URGENT_DAYS` — flag invoices due within this many days (default 3)

3. **Add your open POs**
   ```bash
   cp purchase_orders.example.csv purchase_orders.csv
   ```
   Edit with your real open POs. Schema: `po_number, vendor_name, amount, currency, description, status`.

4. **Run**
   ```bash
   python agent.py
   ```
   Forward vendor invoices to the inbox the agent prints on startup.

## How it works

For each incoming email, the agent:

1. **Fetches the message + attachments.** PDFs and images get pulled via `client.inboxes.messages.get_attachment(...)` — the SDK returns a presigned `download_url` we fetch.
2. **Calls Claude with native PDF vision.** The PDF goes in as a `document` content block; images go in as `image` blocks. Claude calls one of:

   | Tool | When |
   | --- | --- |
   | `extract_invoice(vendor_name, invoice_number, amount, currency, due_date, po_number, line_items, notes)` | Confidently extracted from the document |
   | `cannot_extract(reason)` | Email isn't an invoice OR critical fields missing |

3. **Routes by rule:**

   | Condition | Status | Action |
   | --- | --- | --- |
   | Duplicate `invoice_number` from same vendor | `duplicate` | Reply to vendor, no AP forward, log |
   | No matching open PO | `needs_review_no_po` | Reply asks vendor for PO ref, forward to `AP_EMAIL` |
   | Matched PO + amount > `AUTO_APPROVE_LIMIT` | `needs_review_over_limit` | Forward to `AP_EMAIL` for review |
   | Matched PO + amount ≤ `AUTO_APPROVE_LIMIT` | `auto_approved` | Reply confirming queued for payment |

4. **Marks urgent** if `due_date` is within `URGENT_DAYS` of today. Urgent invoices get a `⚠️ URGENT` line in both the vendor ack and AP forward.

5. **Logs every action** to `invoice_log.csv` and records the processed invoice to `invoices.json` (for duplicate detection).

## PO matching strategy

Two-pass match against `purchase_orders.csv`:

1. **Exact PO number match** (best signal — invoice cites the PO directly).
2. **Vendor name + amount within $1** fallback for invoices that omit the PO ref.

If neither matches, the invoice gets escalated with a "no matching PO" reason in both the vendor ack and the AP cover note.

## Hard rules baked in

- **Never process without an invoice number.** Per the brief — Claude is instructed to call `cannot_extract` if the field is missing, and the code rejects invoices with empty `invoice_number`.
- **Never process duplicates.** Same `invoice_number` + vendor combo gets a polite duplicate reply, no AP forward.
- **Never auto-approve without a PO match.** The brief says "Flag if no PO match" — implemented as a hard `needs_review_no_po` status.

## Files

| File | What it does |
| --- | --- |
| `agent.py` | Polling loop, attachment fetch, Claude vision call, routing logic, vendor ack, AP forward. |
| `prompt.py` | Extraction system prompt. Edit to change the vendor name disambiguation, currency rules, etc. |
| `purchase_orders.py` | CSV-backed PO matcher (exact PO# then vendor+amount fallback). |
| `invoices.py` | `invoices.json` processed-tracker for duplicate detection + `invoice_log.csv` audit log. |
| `purchase_orders.example.csv` | Schema reference + 5 sample POs. |
| `.env.example` | Copy to `.env`. |

## Beyond this template

### Switch to webhooks (recommended for production)

```python
client.webhooks.create(url=..., event_types=["message.received"])
```

### Other upgrades

- **Real ERP integration** — replace `purchase_orders.csv` with a live query against NetSuite / QuickBooks / SAP / Xero. The matcher signature stays the same.
- **3-way match** — extend matching to also verify against goods-received notes (GRN). Common in B2B AP workflows.
- **Auto-payment** — for auto-approved invoices, kick off an actual ACH / wire via Stripe / Mercury / Modern Treasury. Right now the agent stops at "queued for payment."
- **Vendor-specific rules** — `vendors.json` allowlist with per-vendor auto-approve thresholds (e.g., trusted vendors get a higher limit).
- **Fraud detection** — flag invoices where vendor banking details changed since the last paid invoice. Critical control for AP fraud prevention.
