/**
 * AgentMail Approval Inbox — TypeScript port.
 *
 * Per email:
 *   - Reply on a thread with a pending request → parse decision, fire actions
 *   - Else → Claude classifies (extract_request | discard) → review email to user
 */

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import "dotenv/config";
import { AgentMailClient } from "agentmail";
import Anthropic from "@anthropic-ai/sdk";

import { buildClassifyPrompt } from "./prompt.js";
import * as typesConfig from "./typesConfig.js";
import * as requestsStore from "./requestsStore.js";
import * as replyParser from "./replyParser.js";
import * as actions from "./actions.js";

// --- config -------------------------------------------------------------------

const AGENTMAIL_API_KEY = process.env.AGENTMAIL_API_KEY!;
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY!;
const USER_NAME = process.env.USER_NAME || "User";
const USER_EMAIL = process.env.USER_EMAIL!;
const MODEL = process.env.ANTHROPIC_MODEL || "claude-sonnet-4-6";
const POLL_INTERVAL = parseInt(process.env.POLL_INTERVAL_SECONDS || "15", 10);
const INBOX_USERNAME = process.env.INBOX_USERNAME || undefined;

const STATE_FILE = ".agent_state.json";

// --- clients ------------------------------------------------------------------

const agentmail = new AgentMailClient({ apiKey: AGENTMAIL_API_KEY });
const claude = new Anthropic({ apiKey: ANTHROPIC_API_KEY });

// --- Claude tools -------------------------------------------------------------

const CLASSIFY_TOOLS: Anthropic.Tool[] = [
  {
    name: "extract_request",
    description: "Email matches one of the configured request types. Extract fields and summarize.",
    input_schema: {
      type: "object",
      required: ["type", "fields", "summary"],
      properties: {
        type: { type: "string", description: "The matched type name (must match configured)." },
        fields: {
          type: "object",
          description: "Extracted fields keyed by the type's field names. Empty string for missing.",
          additionalProperties: { type: "string" },
        },
        summary: { type: "string", description: "Single line ≤100 chars." },
      },
    },
  },
  {
    name: "discard",
    description: "Email does NOT match any configured request type.",
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
    catch (e: any) { console.log(`(stale state, creating new inbox: ${e.message})`); }
  }
  const inbox = await agentmail.inboxes.create({
    username: INBOX_USERNAME,
    displayName: `${USER_NAME} Approvals`,
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

// --- formatting ---------------------------------------------------------------

function formatReviewEmail(row: requestsStore.RequestRow, fields: Record<string, any>, type: typesConfig.TypeConfig): string {
  const lines = [
    `[${row.type}] ${row.summary}`,
    "",
  ];
  for (const k of type.extract_fields) {
    const v = fields[k] || "(not extracted)";
    lines.push(`  ${k}: ${v}`);
  }
  lines.push("");

  function describe(block: typesConfig.ActionBlock): string {
    const parts: string[] = [];
    if (block.forward_to) parts.push(`forward to ${block.forward_to}`);
    if (block.webhook) parts.push("fire webhook");
    if (block.reply_to_sender) parts.push("reply to original sender");
    return parts.length ? parts.join(", ") : "just record decision";
  }

  lines.push(
    "Reply with one word to decide:",
    `  approve   → ${describe(type.approve)}`,
    `  decline   → ${describe(type.decline)}`,
    `  defer 7d  → snooze, ask again later`,
    `  edit: <text>  → request changes`,
    "",
    `Request id: ${row.id}`,
    "",
    `— Approval inbox`,
  );
  return lines.join("\n");
}

function formatDecisionAck(decision: string, row: requestsStore.RequestRow, confirmations: string[]): string {
  return (
    `Recorded ${decision.toUpperCase()} for [${row.type}] ${row.summary}.\n\n` +
    `Actions taken:\n` +
    confirmations.map(c => `  • ${c}`).join("\n") +
    `\n\nRequest id: ${row.id}\n\n— Approval inbox`
  );
}

// --- core processing ----------------------------------------------------------

async function processMessage(message: any, inbox: any, types: typesConfig.TypeConfig[]): Promise<void> {
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

  // 1. Reply on a pending request thread?
  const pending = requestsStore.findPendingByThread(threadId);
  if (pending) {
    return handleDecisionReply(message, pending, body, types, inbox);
  }

  // 2. Else classify
  if (!types.length) {
    console.warn("  ! no types configured, discarding");
    await markRead(inbox.inboxId, message.messageId, ["unconfigured"]);
    return;
  }

  const response = await claude.messages.create({
    model: MODEL,
    max_tokens: 2048,
    system: buildClassifyPrompt(inbox.email, types),
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

  if (toolUse.name === "discard") {
    const reason = (toolUse.input?.reason || "noise");
    console.log(`  · discard (${reason})`);
    await markRead(inbox.inboxId, message.messageId, ["discarded"]);
    return;
  }

  // extract_request
  const args = toolUse.input || {};
  const typeCfg = typesConfig.find(types, args.type || "");
  if (!typeCfg) {
    console.warn(`  ! Claude returned unknown type '${args.type}', discarding`);
    await markRead(inbox.inboxId, message.messageId, ["unknown-type"]);
    return;
  }

  const fields = args.fields || {};
  const summary = args.summary || "";
  const row = requestsStore.append({
    threadId, type: args.type, summary, fields,
    sourceMessageId: message.messageId, sourceSender: sender,
  });
  console.log(`  ✓ extracted: ${args.type}  (id ${row.id})  fields=${Object.keys(fields)}`);

  try {
    await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
      to: [USER_EMAIL],
      text: formatReviewEmail(row, fields, typeCfg),
    });
    console.log(`  ✓ review email sent to ${USER_EMAIL}`);
  } catch (e: any) {
    console.warn(`  ! review reply failed (sending fresh): ${e.message}`);
    await agentmail.inboxes.messages.send(inbox.inboxId, {
      to: [USER_EMAIL],
      subject: `[Approval needed] ${summary}`,
      text: formatReviewEmail(row, fields, typeCfg),
    });
  }
  await markRead(inbox.inboxId, message.messageId, [`req-${args.type}`, "pending"]);
}

async function handleDecisionReply(message: any, pending: requestsStore.RequestRow, body: string, types: typesConfig.TypeConfig[], inbox: any): Promise<void> {
  const decision = replyParser.parse(body);

  if (decision.decision === "unknown") {
    const firstLine = body.trim().split("\n")[0]?.slice(0, 80) || "";
    console.log(`  ? could not parse decision: '${firstLine}'`);
    try {
      await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
        text:
          "I couldn't parse your reply. Please reply with one of:\n" +
          "  approve\n" +
          "  decline (or 'decline: <reason>')\n" +
          "  defer 7d\n" +
          "  edit: <changes>\n\n" +
          "— Approval inbox",
      });
    } catch {}
    await markRead(inbox.inboxId, message.messageId, ["unparseable"]);
    return;
  }

  const typeCfg = typesConfig.find(types, pending.type);
  if (!typeCfg) {
    console.warn(`  ! type ${pending.type} no longer configured`);
    await markRead(inbox.inboxId, message.messageId, ["stale-type"]);
    return;
  }

  const decidedText = body.trim().split("\n")[0]?.slice(0, 200) || "";
  const statusMap: Record<string, string> = {
    approve: "approved", decline: "declined", defer: "deferred", changes: "changes_requested",
  };
  const newStatus = statusMap[decision.decision];
  requestsStore.updateStatus(pending.id, newStatus, decidedText);
  console.log(`  ✓ decision: ${decision.decision}  (request ${pending.id})`);

  let confirmations: string[] = [];
  if (decision.decision === "approve" || decision.decision === "decline") {
    confirmations = await actions.fire({
      agentmail, inbox, requestRow: pending, typeConfig: typeCfg,
      decision: decision.decision,
      decisionArgs: {
        reason: decision.reason,
        changes_text: decision.changes_text,
      },
    });
  } else if (decision.decision === "defer") {
    confirmations.push(`deferred for ${decision.days || 1} day(s)`);
  } else {
    const ctext = decision.changes_text || "";
    confirmations.push(`marked as changes-requested${ctext ? `: '${ctext.slice(0, 100)}'` : ""}`);
  }

  try {
    await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
      text: formatDecisionAck(decision.decision, pending, confirmations),
    });
  } catch (e: any) {
    console.warn(`  ! ack failed: ${e.message}`);
  }
  await markRead(inbox.inboxId, message.messageId, [`decided-${newStatus}`]);
}

// --- main loop ----------------------------------------------------------------

async function main(): Promise<void> {
  console.log(`--- Approval Inbox  ·  ${USER_NAME} ---`);
  const inbox = await getOrCreateInbox();
  let types = typesConfig.load();

  console.log(`Inbox: ${inbox.email}  (id: ${inbox.inboxId})`);
  console.log(`User:  ${USER_EMAIL}`);
  console.log(`Configured types (${types.length}): ${types.length ? types.map(t => t.type).join(", ") : "(none — edit approval_types.yaml)"}`);
  console.log(`Polling every ${POLL_INTERVAL}s.\n`);

  while (true) {
    try {
      types = typesConfig.load();  // reload each iteration
      const unread: any = await agentmail.inboxes.messages.list(inbox.inboxId, { labels: ["unread"] });
      const messages: any[] = unread.messages || [];
      if (messages.length) {
        console.log(`[${new Date().toISOString()}] ${messages.length} unread`);
        for (const m of messages) {
          try { await processMessage(m, inbox, types); }
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
