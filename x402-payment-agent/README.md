# x402 Payment Agent

> **Autonomous B2B payments via x402.** Vendor invoices land in your inbox, the agent extracts them, validates against your allowlist + cap, and pays via x402 (HTTP 402 + crypto rails like USDC). Off-list or over-cap requests get queued for you to approve with one reply. Built on [AgentMail](https://agentmail.to) + Claude.

Two implementations live in this repo:

- [`python/`](./python) — Python 3.10+
- [`typescript/`](./typescript) — Node.js 18+ / TypeScript

## What it does

For each incoming email, Claude calls **exactly one** of three classifier tools:

| Tool | When | Outcome |
| --- | --- | --- |
| `pay_now(vendor, amount, currency, invoice_url, ...)` | Clearly a payment request from a vendor with all required fields | Validate → if vendor on allowlist + amount ≤ cap + not duplicate → fire payment, receipt to vendor + CC finance |
| `needs_review(reason, partial_fields)` | Looks like payment but missing fields / unfamiliar sender / suspicious | Email user with one-line approve/decline prompt |
| `discard(reason)` | Newsletter / marketing / not a payment | Silently mark read |

Validation in code (not the prompt):
- **Duplicate guard:** same `invoice_number` + `vendor_email` already paid → skip
- **Allowlist:** vendor email must be in `vendors.csv` to auto-pay
- **Per-vendor cap:** each vendor has their own `max_amount_usd` in `vendors.csv`
- **Global cap:** `GLOBAL_MAX_USD` overrides any per-vendor cap

Anything that fails validation falls through to the same human-in-the-loop review flow as `needs_review`. Reply `approve` to fire payment, `decline` (with optional `: <reason>`) to skip.

## Payment adapters

The actual money movement lives behind `PAYMENT_ADAPTER` in `.env`:

| Adapter | What it does |
| --- | --- |
| `mock` *(default)* | Built-in simulator that runs the full x402 wire shape (402 challenge → sign payment → retry with `payment-payload` → 200 + transaction id) **in-memory**. No money required. Demonstrates the architecture end-to-end so you can validate the agent works before wiring real funds. |
| `coinbase` | Stub for Coinbase CDP x402 facilitator (Base Sepolia testnet or mainnet). Fill in `CDP_API_KEY` / `CDP_API_SECRET` / `WALLET_ADDRESS` and replace the stub body in `coinbase_adapter.py` per the docs in that file. |

Pattern: `pay(invoice_url, amount, currency, vendor_name, ...) → {transaction_id, status, network, settled_at}` — write your own adapter for any rail (Stripe Treasury, ACH, manual wire) and drop it in.

## Beyond the bare brief

The original brief said "monitor for payment requests, validate, autonomously pay, reply with confirmation" — but skipped the hard parts: how to *recognize* a real x402 invoice email vs. phishing, what happens to off-list / over-cap requests, how to plug in a real x402 facilitator without forcing every template user through Coinbase CDP setup. We addressed each:

- **Phishing-resistant classification.** Hard rule in the prompt: any urgency-shaped payment request from an unfamiliar sender, or a "banking details changed" notice, gets routed to `needs_review` even if it parses cleanly. Combined with the allowlist guard, the agent will never auto-pay a vendor it's never seen.
- **All paths land in `payments.csv`.** Auto-paid, declined, escalated, duplicate, failed — every classification gets a row with timestamps + decision text. Closes the audit loop the brief implied but didn't define.
- **Adapter pattern.** The actual `pay()` call is one swappable module. Mock ships working out of the box; Coinbase ships as a documented stub showing exactly where to plug in CDP credentials. Most users get a working demo on `git clone`; production users have a clear path.
- **Approval flow reuses the proven pattern** from [approval-inbox](https://github.com/agentmail-to/agentmail-approval-inbox) — same one-word reply parser, same `pending → approved/declined` state machine.
- **Per-vendor caps + global cap.** A vendor can have `max_amount_usd: 5000` in `vendors.csv`, but `GLOBAL_MAX_USD=1000` in `.env` will still gate it. Lower of the two always wins.

## Beyond this template

- **Real x402 facilitator** via Coinbase CDP (Base Sepolia free, Base mainnet for prod) — see `coinbase_adapter.py` for the integration points
- **Webhooks** for production (sub-minute pay latency)
- **Multi-sig wallets** for high-value payments (require 2 human approvals before settlement)
- **Spend categories** with per-category caps (compute / contractors / SaaS / etc.)
- **Anomaly detection** — flag when a known vendor's banking details suddenly change
- **Dashboard** that reads `payments.csv` for monthly spend visibility
