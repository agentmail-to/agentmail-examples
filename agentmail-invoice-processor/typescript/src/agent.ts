/**
 * AgentMail Invoice Processor — TypeScript.
 *
 * For each unread email:
 *   1. Fetch message + any PDF/image attachments
 *   2. Pass body + each attachment to Claude as document/image content blocks
 *   3. Claude calls extract_invoice(...) or cannot_extract(reason)
 *   4. Route deterministically based on routing rules
 *   5. Reply to vendor + (if escalated) forward to AP_EMAIL
 *   6. Log + record for duplicate detection
 */

import "dotenv/config";
import * as fs from "node:fs";
import { AgentMailClient } from "agentmail";
import Anthropic from "@anthropic-ai/sdk";
import * as invoices from "./invoices.js";
import * as purchaseOrders from "./purchaseOrders.js";
import { buildSystemPrompt } from "./prompt.js";

// --- config ------------------------------------------------------------------

const {
  AGENTMAIL_API_KEY,
  ANTHROPIC_API_KEY,
  COMPANY_NAME = "Accounts Payable",
  AP_EMAIL,
  AUTO_APPROVE_LIMIT = "5000",
  URGENT_DAYS = "3",
  ANTHROPIC_MODEL = "claude-sonnet-4-6",
  POLL_INTERVAL_SECONDS = "30",
  INBOX_USERNAME,
} = process.env;

if (!AGENTMAIL_API_KEY) throw new Error("AGENTMAIL_API_KEY required");
if (!ANTHROPIC_API_KEY) throw new Error("ANTHROPIC_API_KEY required");
if (!AP_EMAIL) throw new Error("AP_EMAIL required");

const POLL_MS = Number(POLL_INTERVAL_SECONDS) * 1000;
const AUTO_APPROVE_LIMIT_NUM = Number(AUTO_APPROVE_LIMIT);
const URGENT_DAYS_NUM = Number(URGENT_DAYS);
const STATE_FILE = ".agent_state.json";

const SUPPORTED_DOC_TYPES = new Set([
  "application/pdf",
  "image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp",
]);

// --- clients -----------------------------------------------------------------

const agentmail = new AgentMailClient({ apiKey: AGENTMAIL_API_KEY });
const claude = new Anthropic({ apiKey: ANTHROPIC_API_KEY });

// --- Claude tools ------------------------------------------------------------

const EXTRACT_INVOICE_TOOL = {
  name: "extract_invoice",
  description: "Extract structured fields from an invoice document. Use ONLY when you can confidently identify the required fields verbatim.",
  input_schema: {
    type: "object" as const,
    required: ["vendor_name", "invoice_number", "amount", "currency", "due_date"],
    properties: {
      vendor_name: { type: "string", description: "Company name on the 'Bill From' / letterhead. Not your own company." },
      invoice_number: { type: "string", description: "The invoice ID printed on the document. Verbatim." },
      amount: { type: "number", description: "Grand total amount due (after taxes, fees, discounts)." },
      currency: { type: "string", description: "ISO 4217 code." },
      due_date: { type: "string", description: "Absolute ISO date 'YYYY-MM-DD'. Empty string if not stated." },
      po_number: { type: "string", description: "Purchase order number if cited. Empty string if not." },
      line_items: { type: "string", description: "Brief one-line summary of what was billed." },
      notes: { type: "string", description: "Anything else relevant — early-pay discounts, credit memos, partial billings." },
    },
  },
};

const CANNOT_EXTRACT_TOOL = {
  name: "cannot_extract",
  description: "Email is not an invoice OR critical fields are missing/unreadable.",
  input_schema: {
    type: "object" as const,
    required: ["reason"],
    properties: { reason: { type: "string" } },
  },
};

const TOOLS = [EXTRACT_INVOICE_TOOL, CANNOT_EXTRACT_TOOL];

// --- state -------------------------------------------------------------------

function loadState(): Record<string, any> {
  if (!fs.existsSync(STATE_FILE)) return {};
  try { return JSON.parse(fs.readFileSync(STATE_FILE, "utf8")); }
  catch { return {}; }
}

function saveState(state: Record<string, any>): void {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

// --- helpers -----------------------------------------------------------------

function senderEmail(message: any): string {
  const raw = String(message?.from ?? message?.from_ ?? "");
  const match = raw.match(/<([^>]+)>/);
  return (match ? match[1] : raw).trim().toLowerCase();
}

async function getOrCreateInbox(): Promise<any> {
  const state = loadState();
  if (state.inboxId) {
    try { return await agentmail.inboxes.get(state.inboxId); }
    catch (e: any) { console.log(`(stale state, creating new inbox: ${e.message})`); }
  }
  const inbox = await agentmail.inboxes.create({
    username: INBOX_USERNAME,
    displayName: `${COMPANY_NAME} - Accounts Payable`,
  });
  state.inboxId = inbox.inboxId;
  state.email = inbox.email;
  saveState(state);
  return inbox;
}

async function markRead(inboxId: string, messageId: string, addLabels?: string[]) {
  try {
    await agentmail.inboxes.messages.update(inboxId, messageId, {
      removeLabels: ["unread"],
      addLabels,
    });
  } catch (e: any) {
    console.log(`  ! couldn't mark read: ${e.message}`);
  }
}

async function fetchAttachmentBytes(
  inboxId: string,
  messageId: string,
  attachmentId: string,
): Promise<{ bytes: Buffer; contentType: string } | null> {
  try {
    const meta = await agentmail.inboxes.messages.getAttachment(
      inboxId, messageId, attachmentId,
    );
    const ct = (meta.contentType || "").toLowerCase();
    if (!SUPPORTED_DOC_TYPES.has(ct)) return null;
    const resp = await fetch(meta.downloadUrl);
    if (!resp.ok) {
      console.log(`  ! attachment fetch failed: ${resp.status}`);
      return null;
    }
    const buf = Buffer.from(await resp.arrayBuffer());
    return { bytes: buf, contentType: ct };
  } catch (e: any) {
    console.log(`  ! attachment fetch failed: ${e.message}`);
    return null;
  }
}

function buildContentBlocks(
  textBody: string,
  attachments: { bytes: Buffer; contentType: string; filename: string }[],
): any[] {
  const blocks: any[] = [];
  if (textBody.trim()) {
    blocks.push({ type: "text", text: `Email body:\n${textBody.slice(0, 4000)}` });
  }
  for (const a of attachments) {
    const b64 = a.bytes.toString("base64");
    if (a.contentType === "application/pdf") {
      blocks.push({
        type: "document",
        source: { type: "base64", media_type: a.contentType, data: b64 },
        title: a.filename || "invoice.pdf",
      });
    } else {
      blocks.push({
        type: "image",
        source: { type: "base64", media_type: a.contentType, data: b64 },
      });
    }
  }
  if (!blocks.length) {
    blocks.push({ type: "text", text: "(empty email — no body, no attachments)" });
  }
  return blocks;
}

// --- routing -----------------------------------------------------------------

function isUrgent(dueDateStr: string): { urgent: boolean; days: number | null } {
  if (!dueDateStr) return { urgent: false, days: null };
  const due = new Date(dueDateStr);
  if (isNaN(due.getTime())) return { urgent: false, days: null };
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  due.setHours(0, 0, 0, 0);
  const days = Math.floor((due.getTime() - today.getTime()) / (24 * 60 * 60 * 1000));
  return { urgent: days <= URGENT_DAYS_NUM, days };
}

function vendorAckBody(
  invoice: any,
  status: string,
  urgentDays: number | null,
  poMatch: any,
): string {
  const vendor = invoice.vendor_name || "";
  const invNum = invoice.invoice_number || "";
  const amount = invoice.amount || 0;
  const currency = invoice.currency || "USD";

  const lines: string[] = [
    `Hi ${vendor},`,
    "",
    "Thanks for the invoice. Recording the following:",
    "",
    `  Invoice: ${invNum}`,
    `  Amount: ${amount.toLocaleString("en-US", { minimumFractionDigits: 2 })} ${currency}`,
  ];
  if (invoice.due_date) lines.push(`  Due:    ${invoice.due_date}`);
  if (invoice.po_number) lines.push(`  PO:     ${invoice.po_number}`);
  lines.push("");

  if (status === "auto_approved") {
    const poRef = poMatch ? ` per PO ${poMatch.po_number} terms` : "";
    lines.push(`This invoice has been auto-approved (under our auto-approve limit) and is in the payment queue. You'll receive payment${poRef}.`);
  } else if (status === "needs_review_over_limit") {
    lines.push("This invoice exceeds our auto-approve threshold and has been forwarded to our AP team for review. Expect confirmation within 2 business days.");
  } else if (status === "needs_review_no_po") {
    lines.push("We don't have a matching open purchase order on file for this invoice. Could you confirm the PO reference, or our AP team will follow up shortly?");
  } else if (status === "duplicate") {
    lines.push(`This invoice number was already received and processed. If this is a new charge, please assign a new invoice number and resend.`);
  }

  if (urgentDays !== null && urgentDays <= URGENT_DAYS_NUM) {
    lines.push("");
    lines.push(`⚠️  Note: marked URGENT (due in ${urgentDays} day${urgentDays === 1 ? "" : "s"}).`);
  }

  lines.push("");
  lines.push(`— ${COMPANY_NAME} Accounts Payable`);
  return lines.join("\n");
}

function apForwardBody(
  invoice: any,
  status: string,
  urgentDays: number | null,
  poMatch: any,
  reason: string,
): string {
  const tag = urgentDays !== null && urgentDays <= URGENT_DAYS_NUM ? "[URGENT] " : "";
  const lines: string[] = [
    `${tag}[INVOICE FLAGGED FOR REVIEW]`,
    "",
    `Reason: ${reason}`,
    "",
    `Vendor: ${invoice.vendor_name || ""}`,
    `Invoice #: ${invoice.invoice_number || ""}`,
    `Amount: ${(invoice.amount || 0).toLocaleString("en-US", { minimumFractionDigits: 2 })} ${invoice.currency || ""}`,
    `Due: ${invoice.due_date || "(not specified)"}`,
    `PO cited on invoice: ${invoice.po_number || "(none)"}`,
    `Matched PO: ${poMatch ? `${poMatch.po_number} (${poMatch.description || ""})` : "NONE"}`,
    "",
  ];
  if (invoice.notes) lines.push(`Notes: ${invoice.notes}`);
  if (invoice.line_items) lines.push(`Line items: ${invoice.line_items}`);
  lines.push("");
  lines.push("---");
  lines.push("Original email + invoice attachment forwarded below.");
  return lines.join("\n");
}

// --- core processing ---------------------------------------------------------

async function processMessage(message: any, inbox: any) {
  const full = await agentmail.inboxes.messages.get(inbox.inboxId, message.messageId);

  // Pull text body — prefer whichever is longer (extracted_text sometimes
  // truncates invoice bodies; raw text is more reliable for our purposes).
  const extracted = ((full as any).extractedText || "").trim();
  const raw = (full.text || "").trim();
  const textBody = raw.length > extracted.length * 1.5 ? raw : (extracted || raw);

  // Fetch attachments
  console.log(`  → fetching message + attachments`);
  const fetchedAttachments: { bytes: Buffer; contentType: string; filename: string }[] = [];
  for (const att of (full.attachments || [])) {
    if (!att.attachmentId) continue;
    const fetched = await fetchAttachmentBytes(inbox.inboxId, message.messageId, att.attachmentId);
    if (fetched) {
      fetchedAttachments.push({
        ...fetched,
        filename: att.filename || "attachment.pdf",
      });
    }
  }

  console.log(`  → asking Claude to extract (model=${ANTHROPIC_MODEL}, ${fetchedAttachments.length} attachment(s))`);
  const response = await claude.messages.create({
    model: ANTHROPIC_MODEL,
    max_tokens: 2048,
    system: buildSystemPrompt(inbox.email),
    tools: TOOLS,
    tool_choice: { type: "any" },
    messages: [{ role: "user", content: buildContentBlocks(textBody, fetchedAttachments) }],
  });

  let extractedInvoice: any = null;
  let cannotReason = "";
  for (const block of response.content) {
    if (block.type === "tool_use" && block.name === "extract_invoice") {
      extractedInvoice = block.input;
    } else if (block.type === "tool_use" && block.name === "cannot_extract") {
      cannotReason = (block.input as any).reason || "";
    }
  }

  if (!extractedInvoice) {
    console.log(`  ⏭  cannot extract: ${cannotReason || "(no reason)"}`);
    invoices.logAction({
      action: "rejected", thread_id: message.threadId, note: cannotReason,
    });
    await markRead(inbox.inboxId, message.messageId, ["not_invoice"]);
    return;
  }

  // Hard rule: no invoice number
  const invNum = (extractedInvoice.invoice_number || "").trim();
  const vendor = (extractedInvoice.vendor_name || "").trim();
  if (!invNum) {
    console.log(`  ⏭  no invoice number — rejecting`);
    invoices.logAction({
      action: "rejected", vendor, thread_id: message.threadId,
      note: "Missing invoice number",
    });
    try {
      await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
        text: `Thanks for the email — we couldn't find an invoice number on the document. Please correct and resend with a unique invoice number printed on the invoice.`,
      });
    } catch {}
    await markRead(inbox.inboxId, message.messageId, ["rejected"]);
    return;
  }

  // Hard rule: duplicate
  if (invoices.isDuplicate(invNum, vendor)) {
    console.log(`  ⏭  duplicate ${invNum} from ${vendor}`);
    invoices.logAction({
      action: "rejected", vendor, invoice_number: invNum,
      thread_id: message.threadId, note: "Duplicate invoice number",
    });
    try {
      await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
        text: vendorAckBody(extractedInvoice, "duplicate", null, null),
      });
    } catch {}
    await markRead(inbox.inboxId, message.messageId, ["duplicate"]);
    return;
  }

  // Routing: PO match → auto-approve / over-limit / no-po
  const amount = Number(extractedInvoice.amount || 0);
  const currency = (extractedInvoice.currency || "USD").toUpperCase();
  const poMatch = purchaseOrders.findMatch(
    extractedInvoice.po_number, vendor, amount,
  );
  const { urgent, days } = isUrgent(extractedInvoice.due_date || "");

  let status: string;
  let reason: string;
  if (!poMatch) {
    status = "needs_review_no_po";
    reason = `No matching open PO found for vendor "${vendor}" / amount ${amount} ${currency}.`;
  } else if (amount > AUTO_APPROVE_LIMIT_NUM) {
    status = "needs_review_over_limit";
    reason = `OVER AUTO-APPROVE LIMIT ($${AUTO_APPROVE_LIMIT_NUM}).`;
  } else {
    status = "auto_approved";
    reason = `Matched ${poMatch.po_number}; ${amount} ${currency} ≤ $${AUTO_APPROVE_LIMIT_NUM}.`;
  }

  console.log(`  📄 extracted: ${vendor} #${invNum} ${amount.toLocaleString("en-US", { minimumFractionDigits: 2 })} ${currency} → ${status}`);

  // Vendor ack
  try {
    await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
      text: vendorAckBody(extractedInvoice, status, days, poMatch),
    });
  } catch (e: any) {
    console.log(`    ! vendor ack failed: ${e.message}`);
  }

  // AP forward (only on escalation)
  if (status !== "auto_approved") {
    try {
      const subjectTag = urgent ? "[URGENT] " : "";
      await agentmail.inboxes.messages.forward(inbox.inboxId, message.messageId, {
        to: [AP_EMAIL!],
        text: apForwardBody(extractedInvoice, status, days, poMatch, reason),
      });
      console.log(`  ⚠️  escalation forwarded to ${AP_EMAIL}`);
    } catch (e: any) {
      console.log(`    ! AP forward failed: ${e.message}`);
    }
  }

  // Record + log
  invoices.recordProcessed({
    vendor,
    invoice_number: invNum,
    amount,
    currency,
    due_date: extractedInvoice.due_date || "",
    po_number: extractedInvoice.po_number || "",
    po_match: poMatch?.po_number || "",
    status,
    is_urgent: urgent,
    message_id: message.messageId,
    thread_id: message.threadId,
  });
  invoices.logAction({
    action: "processed", vendor, invoice_number: invNum,
    amount: String(amount), currency,
    due_date: extractedInvoice.due_date || "",
    po_number: poMatch?.po_number || "",
    status, thread_id: message.threadId,
    note: `urgent=${urgent}, po_match=${poMatch?.po_number || "NONE"}`,
  });
  await markRead(inbox.inboxId, message.messageId, [status, urgent ? "urgent" : "normal"]);
}

// --- main loop ---------------------------------------------------------------

async function main() {
  const inbox = await getOrCreateInbox();
  console.log(`\n📬 Invoice processor live at: ${inbox.email}`);
  console.log(`   AP routing: ${AP_EMAIL}`);
  console.log(`   Auto-approve limit: $${AUTO_APPROVE_LIMIT_NUM}`);
  console.log(`   Urgent threshold: ${URGENT_DAYS_NUM} days`);
  console.log(`   POs loaded: ${purchaseOrders.loadAll().length}`);
  console.log(`   Polling every ${POLL_MS / 1000}s. Ctrl-C to stop.\n`);

  const seen = new Set<string>();
  while (true) {
    try {
      const resp = await agentmail.inboxes.messages.list(inbox.inboxId, {
        labels: ["unread"],
      });
      const newMsgs = (resp.messages || []).filter((m: any) => !seen.has(m.messageId));
      for (const m of newMsgs) {
        seen.add(m.messageId);
        if (senderEmail(m) === inbox.email.toLowerCase()) continue;
        console.log(`\n📩 from ${senderEmail(m)}: ${(m.subject || "(no subject)").slice(0, 60)}`);
        try { await processMessage(m, inbox); }
        catch (e: any) { console.log(`  ! error processing: ${e.message}`); }
      }
    } catch (e: any) {
      console.log(`poll error: ${e.message}`);
    }
    await new Promise((r) => setTimeout(r, POLL_MS));
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
