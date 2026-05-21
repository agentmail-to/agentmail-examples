"""
Mock x402 payment adapter — runs the full x402 wire shape in-memory.

The real x402 protocol works like this:
  1. Client calls vendor's payment URL.
  2. Vendor returns 402 Payment Required with a `payment-required` header
     describing accepted schemes, amounts, assets (e.g. USDC), recipients.
  3. Client signs a payment intent matching the requirements.
  4. Client retries the request with `payment-payload` header.
  5. Vendor verifies the payment, settles via the facilitator, returns 200
     with `payment-response` header containing the on-chain transaction id.

This mock simulates the same conversation in-process so you can demo the
template end-to-end without touching real funds. Swap in `coinbase_adapter`
to point at the real Coinbase CDP facilitator on Base Sepolia or mainnet.
"""

import hashlib
import time
from datetime import datetime


class PaymentError(Exception):
    pass


def pay(*, invoice_url: str, amount: float, currency: str,
        vendor_name: str, vendor_email: str, invoice_number: str = "") -> dict:
    """Returns {transaction_id, status, network, settled_at}.
    Raises PaymentError on failure."""
    print(f"  [mock x402] step 1 — GET {invoice_url}")
    time.sleep(0.1)

    # --- Simulated 402 challenge ---
    challenge = {
        "scheme": "exact",
        "amount": amount,
        "asset": currency,
        "recipient": f"0x{hashlib.sha1(vendor_email.encode()).hexdigest()[:40]}",
        "network": "mock",
        "nonce": hashlib.sha1(f"{invoice_url}{time.time()}".encode()).hexdigest()[:16],
    }
    print(f"  [mock x402] step 2 — vendor returned 402, challenge: amount={challenge['amount']} {challenge['asset']}, recipient={challenge['recipient'][:14]}...")

    if amount <= 0:
        raise PaymentError("amount must be > 0")
    if currency not in {"USDC", "USDT", "USD", "ETH"}:
        # Mock accepts a small set; real adapters check facilitator-supported assets
        raise PaymentError(f"unsupported asset: {currency}")

    # --- Simulated payment signing ---
    print(f"  [mock x402] step 3 — signing payment intent")
    time.sleep(0.1)
    payment_payload = hashlib.sha1(
        f"{challenge['nonce']}{amount}{currency}".encode()
    ).hexdigest()

    # --- Simulated retry with payment-payload, vendor settles ---
    print(f"  [mock x402] step 4 — retry GET {invoice_url} with payment-payload")
    time.sleep(0.1)
    transaction_id = "0x" + hashlib.sha256(payment_payload.encode()).hexdigest()[:40]

    print(f"  [mock x402] step 5 — vendor returned 200, settled tx={transaction_id[:12]}...")
    return {
        "transaction_id": transaction_id,
        "status": "settled",
        "network": "mock",
        "settled_at": datetime.utcnow().isoformat(timespec="seconds"),
        "amount": amount,
        "currency": currency,
    }
