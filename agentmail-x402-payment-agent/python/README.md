# x402 Payment Agent — Python

Vendor invoices land in your inbox, the agent extracts them, validates against your allowlist + cap, and pays via x402. Off-list / over-cap requests get queued for one-reply approval. Built on [AgentMail](https://agentmail.to) + Claude.

## Setup (3 minutes)

1. **Install**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in API keys, `USER_EMAIL`, `FINANCE_EMAIL`, `GLOBAL_MAX_USD`.

3. **Set up your vendor allowlist**
   ```bash
   cp vendors.example.csv vendors.csv
   ```
   Edit with your real vendors (their billing email addresses + per-vendor max amount).

4. **Run**
   ```bash
   python agent.py
   ```

The agent uses the `mock` payment adapter by default — runs the full x402 wire shape in-memory so you can demo the architecture without touching real funds. Flip `PAYMENT_ADAPTER=coinbase` in `.env` to use the real Coinbase CDP facilitator (requires CDP signup + funded wallet).

## How it works

For each unread email, Claude calls one of these tools:

| Tool | When |
| --- | --- |
| `pay_now(vendor_name, vendor_email, amount, currency, invoice_url, invoice_number, summary)` | Clearly a payment request with all required fields |
| `needs_review(reason, partial_fields, summary)` | Payment-shaped but missing fields / unfamiliar / suspicious |
| `discard(reason)` | Not a payment |

Then deterministic validation:

| Check | Action |
| --- | --- |
| Duplicate `invoice_number` + `vendor_email` | Skip; reply that it's a dup |
| Vendor not on allowlist | Route to review |
| Amount > vendor's per-vendor cap | Route to review |
| Amount > `GLOBAL_MAX_USD` | Route to review |
| All checks pass | Fire `adapter.pay(...)`; receipt to vendor + CC `FINANCE_EMAIL` |

For review-routed payments: user replies `approve` → fire payment via the same adapter; `decline` (or `decline: <reason>`) → skip, vendor gets nothing.

### Reply parser (review threads)

| Reply | Decision |
| --- | --- |
| `approve` / `pay` / `authorize` / `yes` / `lgtm` / `✅` | `approve` |
| `decline` / `no` / `reject` / `skip` / `❌` | `decline` |
| `decline: <reason>` | `decline` (with reason logged) |

### Payment adapter pattern

```python
def pay(*, invoice_url, amount, currency, vendor_name, vendor_email, invoice_number) -> dict:
    """Returns {transaction_id, status, network, settled_at}.
    Raises PaymentError on failure."""
```

Two adapters ship:

- `mock_adapter.py` — simulates the x402 conversation (402 challenge → sign → 200 + tx_id). Used by default.
- `coinbase_adapter.py` — stubbed; documents the real Coinbase CDP integration with TODO markers showing where to drop in CDP keys + the protocol calls.

Set `PAYMENT_ADAPTER=mock` (default) or `coinbase` in `.env`.

## Files

| File | What it does |
| --- | --- |
| `agent.py` | Polling loop, classifier, validation, adapter dispatch, review flow. |
| `prompt.py` | Three-tool classifier prompt. |
| `vendors_store.py` | `vendors.csv` allowlist + per-vendor cap lookup. |
| `payments_store.py` | `payments.csv` audit log + dedup + status updates. |
| `reply_parser.py` | Parses approve/decline on review threads. |
| `mock_adapter.py` | Built-in x402 wire-shape simulator. |
| `coinbase_adapter.py` | Stub for real Coinbase CDP facilitator (TODOs). |

## Beyond this template

- **Real x402 facilitator** via Coinbase CDP — see `coinbase_adapter.py`
- **Webhooks** for production
- **Multi-sig wallets** for high-value (require 2 human approvals)
- **Spend categories** with per-category caps
- **Anomaly detection** — flag changed banking details
- **Dashboard** over `payments.csv`
