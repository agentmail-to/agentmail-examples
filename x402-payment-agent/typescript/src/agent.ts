/**
 * AgentMail x402 Payment Agent — TypeScript port.
 *
 * Per email:
 *   A. Reply on a thread with a pending review → parse approve/decline, fire payment
 *   B. New email → Claude classifies (pay_now / needs_review / discard)
 *      → pay_now: validate (allowlist + cap + dedup) → fire adapter OR route to review
 *      → needs_review: log pending, email user for sign-off
 *      → discard: silently mark read
 */

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import "dotenv/config";
import { AgentMailClient } from "agentmail";
import Anthropic from "@anthropic-ai/sdk";

import { buildClassifyPrompt } from "./prompt.js";
import * as vendorsStore from "./vendorsStore.js";
import * as paymentsStore from "./paymentsStore.js";
import * as replyParser from "./replyParser.js";

// Adapter selection
import * as mockAdapter from "./mockAdapter.js";
import * as coinbaseAdapter from "./coinbaseAdapter.js";

// --- config -------------------------------------------------------------------

const AGENTMAIL_API_KEY = process.env.AGENTMAIL_API_KEY!;
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY!;
const COMPANY_NAME = process.env.COMPANY_NAME || "Acme";
const USER_EMAIL = process.env.USER_EMAIL!;
const FINANCE_EMAIL = process.env.FINANCE_EMAIL || "";
const GLOBAL_MAX_USD = parseFloat(process.env.GLOBAL_MAX_USD || "1000");
const PAYMENT_CURRENCY = process.env.PAYMENT_CURRENCY || "USDC";
const PAYMENT_ADAPTER_NAME = process.env.PAYMENT_ADAPTER || "mock";
const MODEL = process.env.ANTHROPIC_MODEL || "claude-sonnet-4-6";
const POLL_INTERVAL = parseInt(process.env.POLL_INTERVAL_SECONDS || "15", 10);
const INBOX_USERNAME = process.env.INBOX_USERNAME || undefined;

const STATE_FILE = ".agent_state.json";

const adapter = PAYMENT_ADAPTER_NAME === "coinbase" ? coinbaseAdapter : mockAdapter;
if (!["mock", "coinbase"].includes(PAYMENT_ADAPTER_NAME)) {
  throw new Error(`unknown PAYMENT_ADAPTER: ${PAYMENT_ADAPTER_NAME}`);
}

const agentmail = new AgentMailClient({ apiKey: AGENTMAIL_API_KEY });
const claude = new Anthropic({ apiKey: ANTHROPIC_API_KEY });

// --- Claude tools -------------------------------------------------------------

const CLASSIFY_TOOLS: Anthropic.Tool[] = [
  {
    name: "pay_now",
    description: "Email is a payment request from a vendor with all required fields.",
    input_schema: {
      type: "object",
      required: ["vendor_name", "vendor_email", "amount", "currency", "invoice_url", "summary"],
      properties: {
        vendor_name: { type: "string" },
        vendor_email: { type: "string" },
        amount: { type: "number" },
        currency: { type: "string", enum: ["USDC", "USD", "USDT", "ETH"] },
        invoice_url: { type: "string" },
        invoice_number: { type: "string" },
        summary: { type: "string" },
      },
    },
  },
  {
    name: "needs_review",
    description: "Looks like a payment request but agent shouldn't fire pay_now.",
    input_schema: {
      type: "object",
      required: ["reason", "summary"],
      properties: {
        reason: { type: "string" },
        partial_fields: { type: "object", additionalProperties: { type: "string" } },
        summary: { type: "string" },
      },
    },
  },
  {
    name: "discard",
    description: "Not a payment request.",
    input_schema: {
      type: "object",
      required: ["reason"],
      properties: { reason: { type: "string" } },
    },
  },
];

// --- state --------------------------------------------------------------------

function loadState(): Record<string, any> {
  if (!existsSync(STATE_FILE)) return {};
  try { return JSON.parse(readFileSync(STATE_FILE, "utf-8")); } catch { return {}; }
}

function saveState(s: Record<string, any>): void {
  writeFileSync(STATE_FILE, JSON.stringify(s, null, 2));
}

// --- helpers ------------------------------------------------------------------

function senderEmail(message: any): string {
  const from = message.from_ ?? message.from ?? "";
  const m = String(from).match(/<([^>]+)>/);
  return (m ? m[1] : String(from)).trim().toLowerCase();
}

async function getOrCreateInbox(): Promise<any> {
  const state = loadState();
  if (state.inbox_id) {
    try { return await agentmail.inboxes.get(state.inbox_id); }
    catch (e: any) { console.log(`(stale state, creating new: ${e.message})`); }
  }
  const inbox = await agentmail.inboxes.create({
    username: INBOX_USERNAME,
    displayName: `${COMPANY_NAME} Pay Agent`,
  });
  state.inbox_id = inbox.inboxId;
  state.email = inbox.email;
  saveState(state);
  return inbox;
}

async function markRead(inboxId: string, messageId: string, addLabels: string[] = []): Promise<void> {
  try {
    await agentmail.inboxes.messages.update(inboxId, messageId, {
      removeLabels: ["unread"], addLabels,
    });
  } catch (e: any) {
    console.warn(`  ! couldn't mark read: ${e.message}`);
  }
}

async function findPendingInThread(inbox: any, threadId: string): Promise<paymentsStore.PaymentRow | null> {
  if (!threadId) return null;
  try {
    const thread: any = await agentmail.threads.get(threadId);
    const ids = new Set<string>((thread.messages || []).map((m: any) => m.messageId));
    return paymentsStore.findPendingInThreadIds(ids);
  } catch (e: any) {
    console.warn(`  ! thread lookup failed: ${e.message}`);
    return null;
  }
}

// --- core processing ----------------------------------------------------------

async function processMessage(message: any, inbox: any, vendors: vendorsStore.Vendor[]): Promise<void> {
  const full: any = await agentmail.inboxes.messages.get(inbox.inboxId, message.messageId);
  const extracted = (full.extractedText ?? "").trim();
  const raw = (full.text ?? "").trim();
  const body = raw.length > extracted.length * 1.5 ? raw : (extracted || raw);

  const sender = senderEmail(message);
  const subject = (message.subject ?? "") as string;
  const threadId = full.threadId ?? "";
  console.log(`  → ${sender}  ·  '${subject.slice(0, 60)}'  ·  thread ${threadId.slice(0, 24)}`);

  if (sender === inbox.email.toLowerCase()) {
    console.log("  · skipping our own outgoing reply");
    await markRead(inbox.inboxId, message.messageId);
    return;
  }

  // Reply on a pending review thread?
  const pending = await findPendingInThread(inbox, threadId);
  if (pending) return handleReviewReply(message, pending, body, inbox);

  // Else classify
  const response = await claude.messages.create({
    model: MODEL,
    max_tokens: 2048,
    system: buildClassifyPrompt(inbox.email),
    tools: CLASSIFY_TOOLS,
    tool_choice: { type: "any" },
    messages: [{
      role: "user",
      content: `From: ${sender}\nSubject: ${subject}\n\n${body ? body.slice(0, 8000) : "(empty body)"}`,
    }],
  });

  const toolUse = response.content.find((b: any) => b.type === "tool_use") as any;
  if (!toolUse) {
    console.warn("  ! Claude returned no tool call");
    await markRead(inbox.inboxId, message.messageId, ["error"]);
    return;
  }
  const args = toolUse.input || {};
  console.log(`  ✓ classification: ${toolUse.name}`);

  if (toolUse.name === "discard") {
    await markRead(inbox.inboxId, message.messageId, ["discarded"]);
    return;
  }
  if (toolUse.name === "needs_review") {
    return routeToReview(message, args, inbox, sender, args.reason || "manual_review");
  }

  // pay_now
  return handlePayNow(message, args, inbox, vendors, sender);
}

async function handlePayNow(message: any, args: any, inbox: any, vendors: vendorsStore.Vendor[], sender: string): Promise<void> {
  const vendorEmail = (args.vendor_email || sender).toLowerCase();
  const vendorName = args.vendor_name || vendorEmail;
  const amount = parseFloat(args.amount) || 0;
  const currency = args.currency || PAYMENT_CURRENCY;
  const invoiceUrl = args.invoice_url || "";
  const invoiceNumber = args.invoice_number || "";

  // 1. Duplicate
  if (invoiceNumber && paymentsStore.isDuplicate(invoiceNumber, vendorEmail)) {
    console.log(`  · duplicate invoice ${invoiceNumber} from ${vendorEmail} — skipping`);
    try {
      await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
        text:
          `This invoice (${invoiceNumber}) was already received and processed. ` +
          `If this is in error, contact ${USER_EMAIL}.\n\n— ${COMPANY_NAME} Pay Agent`,
      });
    } catch {}
    paymentsStore.append({
      vendorName, vendorEmail, amount, currency, invoiceNumber,
      decision: "duplicate", status: "skipped",
      sourceMessageId: message.messageId,
    });
    await markRead(inbox.inboxId, message.messageId, ["duplicate"]);
    return;
  }

  // 2. Allowlist
  const vendor = vendorsStore.find(vendors, vendorEmail);
  if (!vendor) {
    console.log(`  · ${vendorEmail} not on allowlist — review`);
    return routeToReview(message, args, inbox, sender, "vendor_not_on_allowlist", amount, currency, invoiceNumber);
  }

  // 3. Cap
  const cap = Math.min(vendor.max_amount_usd, GLOBAL_MAX_USD);
  if (amount > cap) {
    console.log(`  · $${amount} > cap $${cap} — review`);
    return routeToReview(message, args, inbox, sender,
      `amount_$${amount}_exceeds_cap_$${cap}`, amount, currency, invoiceNumber);
  }

  // 4. Pay
  console.log(`  → AUTO-PAYING $${amount.toFixed(2)} ${currency} to ${vendorName}`);
  const row = paymentsStore.append({
    vendorName, vendorEmail, amount, currency, invoiceNumber,
    decision: "auto_approved", status: "paying",
    sourceMessageId: message.messageId,
  });

  let result: mockAdapter.PaymentResult;
  try {
    result = await adapter.pay({
      invoiceUrl, amount, currency, vendorName, vendorEmail, invoiceNumber,
    });
  } catch (e: any) {
    console.warn(`  ! payment failed: ${e.message}`);
    paymentsStore.updateStatus(row.id, "failed", "", "auto_approved");
    try {
      await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
        text: `Payment failed: ${e.message}\n\nRouting to ${USER_EMAIL} for manual handling.`,
      });
    } catch {}
    await markRead(inbox.inboxId, message.messageId, ["payment-failed"]);
    return;
  }

  // 5. Receipt to vendor + CC finance
  paymentsStore.updateStatus(row.id, "paid", result.transaction_id);
  const receipt =
    `Hi ${vendorName},\n\n` +
    `Confirming payment of ${amount.toFixed(2)} ${currency} for invoice ${invoiceNumber || "(no invoice number)"}.\n\n` +
    `Transaction id: ${result.transaction_id}\n` +
    `Network:        ${result.network}\n` +
    `Settled at:     ${result.settled_at}\n\n` +
    `Thank you,\n${COMPANY_NAME}`;

  try {
    const replyArgs: any = { text: receipt };
    if (FINANCE_EMAIL) replyArgs.cc = [FINANCE_EMAIL];
    await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, replyArgs);
  } catch (e: any) {
    console.warn(`  ! receipt failed: ${e.message}`);
  }

  console.log(`  ✓ paid · tx=${result.transaction_id.slice(0, 14)}...`);
  await markRead(inbox.inboxId, message.messageId, ["paid"]);
}

async function routeToReview(message: any, args: any, inbox: any, sender: string, reason: string,
                              rowAmount?: number, rowCurrency?: string, rowInvoice?: string): Promise<void> {
  const partial = args.partial_fields || {};
  const vendorName = args.vendor_name || partial.vendor_name || sender;
  const vendorEmail = (args.vendor_email || partial.vendor_email || sender).toLowerCase();
  const amount = rowAmount ?? parseFloat(partial.amount || args.amount || "0");
  const currency = rowCurrency || partial.currency || args.currency || PAYMENT_CURRENCY;
  const invoiceNumber = rowInvoice || partial.invoice_number || args.invoice_number || "";
  const summary = args.summary || "";

  const row = paymentsStore.append({
    vendorName, vendorEmail, amount, currency, invoiceNumber,
    decision: "needs_review", status: "pending_review",
    sourceMessageId: message.messageId,
  });

  const reviewBody =
    `[needs review · ${reason}]\n\n` +
    `Summary: ${summary}\n\n` +
    `  Vendor:  ${vendorName} (${vendorEmail})\n` +
    `  Amount:  ${amount.toFixed(2)} ${currency}\n` +
    `  Invoice: ${invoiceNumber || "(none)"}\n` +
    `  Reason:  ${reason}\n\n` +
    `Reply to this thread with one word:\n` +
    `  approve  → fire payment via ${PAYMENT_ADAPTER_NAME} adapter\n` +
    `  decline  → skip; vendor gets nothing\n` +
    `  decline: <reason>  → skip with reason logged\n\n` +
    `Payment id: ${row.id}\n\n— ${COMPANY_NAME} Pay Agent`;

  try {
    await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
      to: [USER_EMAIL],
      text: reviewBody,
    });
    console.log(`  ✓ review email sent to ${USER_EMAIL}`);
  } catch (e: any) {
    console.warn(`  ! review send failed: ${e.message}`);
  }
  await markRead(inbox.inboxId, message.messageId, ["needs-review"]);
}

async function handleReviewReply(message: any, pending: paymentsStore.PaymentRow, body: string, inbox: any): Promise<void> {
  const decision = replyParser.parse(body);

  if (decision.decision === "unknown") {
    try {
      await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
        text:
          `I couldn't parse your reply. Please reply with:\n` +
          `  approve  → pay\n  decline  → skip\n  decline: <reason>  → skip with reason\n\n` +
          `— ${COMPANY_NAME} Pay Agent`,
      });
    } catch {}
    await markRead(inbox.inboxId, message.messageId, ["unparseable"]);
    return;
  }

  const decidedText = body.trim().split("\n")[0]?.slice(0, 200) || "";

  if (decision.decision === "decline") {
    const reason = decision.reason || "";
    paymentsStore.updateStatus(pending.id, "skipped", "", reason ? `declined: ${reason}` : "declined");
    try {
      await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
        text:
          `Skipped payment. Vendor was NOT contacted.\n\nDecision: ${decidedText}\n\n` +
          `Payment id: ${pending.id}\n\n— ${COMPANY_NAME} Pay Agent`,
      });
    } catch {}
    await markRead(inbox.inboxId, message.messageId, ["declined"]);
    return;
  }

  // Approve → fire adapter
  const amount = parseFloat(pending.amount);
  console.log(`  → user approved $${amount.toFixed(2)} ${pending.currency} to ${pending.vendor_name} — paying`);
  let result: mockAdapter.PaymentResult;
  try {
    result = await adapter.pay({
      invoiceUrl: "",
      amount,
      currency: pending.currency,
      vendorName: pending.vendor_name,
      vendorEmail: pending.vendor_email,
      invoiceNumber: pending.invoice_number,
    });
  } catch (e: any) {
    paymentsStore.updateStatus(pending.id, "failed", "", "user_approved");
    try {
      await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
        text: `Payment failed even after approval: ${e.message}\n\nPayment id: ${pending.id}`,
      });
    } catch {}
    await markRead(inbox.inboxId, message.messageId, ["payment-failed"]);
    return;
  }

  paymentsStore.updateStatus(pending.id, "paid", result.transaction_id, "user_approved");

  // Receipt to vendor on the original thread
  const receipt =
    `Hi ${pending.vendor_name},\n\n` +
    `Confirming payment of ${amount.toFixed(2)} ${pending.currency} for invoice ${pending.invoice_number || "(no invoice number)"}.\n\n` +
    `Transaction id: ${result.transaction_id}\n` +
    `Network:        ${result.network}\n\n` +
    `Thank you,\n${COMPANY_NAME}`;

  try {
    const replyArgs: any = { text: receipt };
    if (FINANCE_EMAIL) replyArgs.cc = [FINANCE_EMAIL];
    await agentmail.inboxes.messages.reply(inbox.inboxId, pending.source_message_id, replyArgs);
  } catch (e: any) {
    console.warn(`  ! receipt to vendor failed: ${e.message}`);
  }

  // Ack to user
  try {
    await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
      text:
        `Paid ${amount.toFixed(2)} ${pending.currency} to ${pending.vendor_name}.\n\n` +
        `Transaction id: ${result.transaction_id}\n` +
        `Receipt sent to vendor (cc ${FINANCE_EMAIL || "none"}).\n\n` +
        `Payment id: ${pending.id}\n\n— ${COMPANY_NAME} Pay Agent`,
    });
  } catch {}

  await markRead(inbox.inboxId, message.messageId, ["paid-after-review"]);
}

// --- main loop ----------------------------------------------------------------

async function main(): Promise<void> {
  console.log(`--- x402 Payment Agent  ·  ${COMPANY_NAME} ---`);
  const inbox = await getOrCreateInbox();
  let vendors = vendorsStore.load();
  console.log(`Inbox:    ${inbox.email}`);
  console.log(`Adapter:  ${PAYMENT_ADAPTER_NAME}`);
  console.log(`Vendors:  ${vendors.length} on allowlist`);
  console.log(`Caps:     per-vendor (vendors.csv) capped further by GLOBAL_MAX_USD=${GLOBAL_MAX_USD}`);
  console.log(`Polling every ${POLL_INTERVAL}s.\n`);

  while (true) {
    try {
      vendors = vendorsStore.load();
      const unread: any = await agentmail.inboxes.messages.list(inbox.inboxId, { labels: ["unread"] });
      const messages: any[] = unread.messages || [];
      if (messages.length) {
        console.log(`[${new Date().toISOString()}] ${messages.length} unread`);
        for (const m of messages) {
          try { await processMessage(m, inbox, vendors); }
          catch (e: any) { console.error(`  ! error on ${m.messageId}: ${e.message}`); }
        }
      }
    } catch (e: any) {
      console.error(`! poll loop error: ${e.message}`);
    }
    await new Promise(r => setTimeout(r, POLL_INTERVAL * 1000));
  }
}

main().catch(e => { console.error(e); process.exit(1); });
