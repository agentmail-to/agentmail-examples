/**
 * Coinbase CDP x402 facilitator adapter — STUBBED.
 *
 * To enable real x402 payments via Coinbase's facilitator:
 *
 *   1. Sign up for Coinbase Developer Platform: https://www.coinbase.com/developer-platform
 *      Generate API key + secret; set CDP_API_KEY and CDP_API_SECRET in .env.
 *
 *   2. Deploy a wallet on Base Sepolia (testnet) or Base (mainnet). Coinbase's
 *      SDK can manage the keypair for you, or BYOW (bring your own wallet)
 *      and provide WALLET_ADDRESS in .env.
 *
 *   3. Fund with testnet USDC (free): https://faucet.circle.com
 *
 *   4. Install the SDK:
 *          npm install @coinbase/cdp-sdk x402
 *
 *   5. Replace the stub below with real protocol calls. Coinbase x402 docs:
 *      https://docs.cdp.coinbase.com/x402
 *
 *      Roughly:
 *
 *          import { CdpClient } from "@coinbase/cdp-sdk";
 *          import { signPayment, parse402Response, formatPaymentHeader } from "x402";
 *
 *          const client = new CdpClient({
 *            apiKey: process.env.CDP_API_KEY!,
 *            apiSecret: process.env.CDP_API_SECRET!,
 *          });
 *
 *          const r1 = await fetch(args.invoiceUrl);
 *          if (r1.status !== 402) throw new PaymentError(`vendor didn't issue 402: got ${r1.status}`);
 *          const challenge = parse402Response(r1.headers.get("payment-required")!);
 *
 *          if (challenge.amount !== args.amount || challenge.asset !== args.currency) {
 *            throw new PaymentError(`challenge mismatch`);
 *          }
 *
 *          const payload = await client.signX402Payment(challenge, {
 *            walletAddress: process.env.WALLET_ADDRESS!,
 *            network: process.env.PAYMENT_NETWORK || "base-sepolia",
 *          });
 *          const r2 = await fetch(args.invoiceUrl, {
 *            headers: { "payment-payload": formatPaymentHeader(payload) },
 *          });
 *          if (r2.status !== 200) throw new PaymentError(`settlement failed: ${r2.status}`);
 *
 *          return {
 *            transaction_id: r2.headers.get("payment-response-transaction-id")!,
 *            status: "settled",
 *            network: process.env.PAYMENT_NETWORK || "base-sepolia",
 *            settled_at: new Date().toISOString().slice(0, 19),
 *            amount: args.amount, currency: args.currency,
 *          };
 *
 *   6. Live-test against Base Sepolia first; flip PAYMENT_NETWORK=base when ready.
 *
 * This file is intentionally stubbed to avoid forcing template users through
 * CDP setup before they can run the demo. The mockAdapter demonstrates the
 * full wire shape; this file shows production wiring.
 */

import { PaymentError, PaymentResult } from "./mockAdapter.js";

export { PaymentError } from "./mockAdapter.js";

export async function pay(_args: any): Promise<PaymentResult> {
  throw new PaymentError(
    "coinbaseAdapter is stubbed. To enable: install @coinbase/cdp-sdk + x402, " +
    "set CDP_API_KEY / CDP_API_SECRET / WALLET_ADDRESS in .env, and replace this " +
    "function with the protocol calls documented in the file header. " +
    "https://docs.cdp.coinbase.com/x402"
  );
}
