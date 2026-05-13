"""
Coinbase CDP x402 facilitator adapter — STUBBED.

To enable real x402 payments via Coinbase's facilitator service:

  1. Sign up for Coinbase Developer Platform: https://www.coinbase.com/developer-platform
     Generate API key + secret; set CDP_API_KEY and CDP_API_SECRET in .env.

  2. Deploy a wallet on Base Sepolia (testnet) or Base (mainnet). Coinbase's
     SDK can manage the keypair for you, or you can BYOW (bring your own wallet)
     and just provide WALLET_ADDRESS in .env.

  3. Fund the wallet with testnet USDC (free) or real USDC depending on network.
     Testnet faucet: https://faucet.circle.com

  4. Install the SDK:
         pip install cdp-sdk x402

  5. Replace the stub below with real protocol calls. The Coinbase x402 docs:
     https://docs.cdp.coinbase.com/x402

     The full flow looks roughly like:

         from cdp_sdk import CdpClient
         from x402 import sign_payment, parse_402_response, format_payment_header

         client = CdpClient(api_key=CDP_API_KEY, api_secret=CDP_API_SECRET)

         r1 = httpx.get(invoice_url)
         if r1.status_code != 402:
             raise PaymentError(f"vendor didn't issue 402: got {r1.status_code}")
         challenge = parse_402_response(r1.headers["payment-required"])

         # Verify challenge matches what we expect (amount, asset, network)
         if challenge.amount != amount or challenge.asset != currency:
             raise PaymentError(f"challenge mismatch: vendor wants {challenge.amount} {challenge.asset}, expected {amount} {currency}")

         # Sign + settle via the Coinbase facilitator
         payload = client.sign_x402_payment(
             challenge, wallet_address=WALLET_ADDRESS, network=PAYMENT_NETWORK,
         )
         r2 = httpx.get(invoice_url, headers={"payment-payload": format_payment_header(payload)})
         if r2.status_code != 200:
             raise PaymentError(f"settlement failed: {r2.status_code} {r2.text}")

         tx_id = r2.headers.get("payment-response-transaction-id")
         return {"transaction_id": tx_id, "status": "settled", ...}

  6. Live-test against Base Sepolia first (free testnet USDC). Once confirmed,
     flip PAYMENT_NETWORK=base in .env.

This file is intentionally not implemented to avoid forcing every template
user to set up a CDP account before they can run the demo. The mock_adapter
demonstrates the full wire shape; this file shows the production wiring.
"""

import os

from mock_adapter import PaymentError


def pay(*, invoice_url: str, amount: float, currency: str,
        vendor_name: str, vendor_email: str, invoice_number: str = "") -> dict:
    raise PaymentError(
        "coinbase_adapter is stubbed. To enable: install `cdp-sdk` and `x402`, "
        "fill CDP_API_KEY / CDP_API_SECRET / WALLET_ADDRESS in .env, and replace "
        "this function body with the protocol calls documented in this file. "
        "See https://docs.cdp.coinbase.com/x402"
    )
