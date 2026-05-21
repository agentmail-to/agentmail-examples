# x402 Payment Agent — TypeScript

Vendor invoices land in your inbox, the agent extracts them, validates against your allowlist + cap, and pays via x402. Off-list / over-cap requests get queued for one-reply approval. Built on [AgentMail](https://agentmail.to) + Claude.

## Setup (3 minutes)

1. **Install**
   ```bash
   npm install
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in API keys, `USER_EMAIL`, `FINANCE_EMAIL`, `GLOBAL_MAX_USD`.

3. **Vendor allowlist**
   ```bash
   cp vendors.example.csv vendors.csv
   ```
   Edit with your real vendors (their billing email + per-vendor max amount).

4. **Run**
   ```bash
   npm start
   ```

The default `mock` payment adapter runs the full x402 wire shape in-memory — no real money required, demonstrates the architecture end-to-end. Flip `PAYMENT_ADAPTER=coinbase` in `.env` to use the real Coinbase CDP facilitator.

## How it works

For each unread email, Claude calls one of these tools:

| Tool | When |
| --- | --- |
| `pay_now(...)` | Clearly a payment request from a vendor with all fields |
| `needs_review(reason, partial_fields)` | Payment-shaped but missing fields / suspicious |
| `discard(reason)` | Not a payment |

Then deterministic validation:

| Check | Action |
| --- | --- |
| Duplicate `invoice_number` + `vendor_email` | Skip |
| Vendor not on allowlist | Route to review |
| Amount > vendor's per-vendor cap | Route to review |
| Amount > `GLOBAL_MAX_USD` | Route to review |
| All checks pass | Fire `adapter.pay(...)`; receipt to vendor + CC `FINANCE_EMAIL` |

For review-routed payments: user replies `approve` → fire payment via the same adapter; `decline` (or `decline: <reason>`) → skip.

### Payment adapter pattern

```ts
async function pay(args: {
  invoiceUrl: string;
  amount: number;
  currency: string;
  vendorName: string;
  vendorEmail: string;
  invoiceNumber?: string;
}): Promise<{transaction_id, status, network, settled_at}>
```

Two adapters ship:

- `mockAdapter.ts` — simulates the x402 conversation (402 challenge → sign → 200 + tx_id).
- `coinbaseAdapter.ts` — stubbed; documents the real CDP integration with TODO markers.

## Files

| File | What it does |
| --- | --- |
| `src/agent.ts` | Polling loop, classifier, validation, adapter dispatch, review flow. |
| `src/prompt.ts` | Three-tool classifier prompt. |
| `src/vendorsStore.ts` | `vendors.csv` allowlist + per-vendor cap lookup. |
| `src/paymentsStore.ts` | `payments.csv` audit log + dedup + status updates. |
| `src/replyParser.ts` | Parses approve/decline on review threads. |
| `src/mockAdapter.ts` | Built-in x402 wire-shape simulator. |
| `src/coinbaseAdapter.ts` | Stub for real Coinbase CDP facilitator. |

## Beyond this template

- **Real x402 facilitator** via Coinbase CDP — see `src/coinbaseAdapter.ts`
- **Webhooks** for production
- **Multi-sig wallets** for high-value (require 2 human approvals)
- **Spend categories** with per-category caps
- **Anomaly detection** for changed banking details
- **Dashboard** over `payments.csv`
