/**
 * Mock x402 payment adapter — runs the full x402 wire shape in-memory.
 *
 * Real x402 protocol:
 *   1. Client GETs vendor's payment URL.
 *   2. Vendor returns 402 with `payment-required` header (scheme, amount, asset, recipient).
 *   3. Client signs payment intent matching the requirements.
 *   4. Client retries with `payment-payload` header.
 *   5. Vendor verifies, settles via the facilitator, returns 200 with tx id.
 *
 * This mock simulates the same conversation in-process so you can demo the
 * template end-to-end without touching real funds. Swap in the Coinbase
 * adapter to point at a real x402 facilitator.
 */

import { createHash } from "node:crypto";

export class PaymentError extends Error {}

export interface PaymentResult {
  transaction_id: string;
  status: string;
  network: string;
  settled_at: string;
  amount: number;
  currency: string;
}

export async function pay(args: {
  invoiceUrl: string;
  amount: number;
  currency: string;
  vendorName: string;
  vendorEmail: string;
  invoiceNumber?: string;
}): Promise<PaymentResult> {
  console.log(`  [mock x402] step 1 — GET ${args.invoiceUrl}`);
  await sleep(100);

  // Simulated 402 challenge
  const challenge = {
    scheme: "exact",
    amount: args.amount,
    asset: args.currency,
    recipient: "0x" + createHash("sha1").update(args.vendorEmail).digest("hex").slice(0, 40),
    network: "mock",
    nonce: createHash("sha1").update(`${args.invoiceUrl}${Date.now()}`).digest("hex").slice(0, 16),
  };
  console.log(`  [mock x402] step 2 — vendor returned 402, challenge: amount=${challenge.amount} ${challenge.asset}, recipient=${challenge.recipient.slice(0, 14)}...`);

  if (args.amount <= 0) throw new PaymentError("amount must be > 0");
  if (!["USDC", "USDT", "USD", "ETH"].includes(args.currency)) {
    throw new PaymentError(`unsupported asset: ${args.currency}`);
  }

  // Simulated payment signing
  console.log(`  [mock x402] step 3 — signing payment intent`);
  await sleep(100);
  const paymentPayload = createHash("sha1")
    .update(`${challenge.nonce}${args.amount}${args.currency}`)
    .digest("hex");

  // Simulated retry + settle
  console.log(`  [mock x402] step 4 — retry GET ${args.invoiceUrl} with payment-payload`);
  await sleep(100);
  const transactionId = "0x" + createHash("sha256").update(paymentPayload).digest("hex").slice(0, 40);

  console.log(`  [mock x402] step 5 — vendor returned 200, settled tx=${transactionId.slice(0, 12)}...`);
  return {
    transaction_id: transactionId,
    status: "settled",
    network: "mock",
    settled_at: new Date().toISOString().slice(0, 19),
    amount: args.amount,
    currency: args.currency,
  };
}

function sleep(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms));
}
