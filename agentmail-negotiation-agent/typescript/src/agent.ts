/**
 * AgentMail Negotiation Agent — TypeScript.
 */

import "dotenv/config";
import * as fs from "node:fs";
import { AgentMailClient } from "agentmail";
import Anthropic from "@anthropic-ai/sdk";
import * as deal from "./deal.js";
import {
  buildReplyClassifierPrompt,
  buildRoundSummaryPrompt,
  buildWriterPrompt,
} from "./prompt.js";

// --- config ------------------------------------------------------------------

const {
  AGENTMAIL_API_KEY,
  ANTHROPIC_API_KEY,
  BUYER_EMAIL,
  ANTHROPIC_MODEL = "claude-sonnet-4-6",
  POLL_INTERVAL_SECONDS = "30",
  INBOX_USERNAME,
} = process.env;

if (!AGENTMAIL_API_KEY) throw new Error("AGENTMAIL_API_KEY required");
if (!ANTHROPIC_API_KEY) throw new Error("ANTHROPIC_API_KEY required");
if (!BUYER_EMAIL) throw new Error("BUYER_EMAIL required");

const BUYER_EMAIL_LC = BUYER_EMAIL.toLowerCase();
const POLL_MS = Number(POLL_INTERVAL_SECONDS) * 1000;
const STATE_FILE = ".agent_state.json";

// --- clients -----------------------------------------------------------------

const agentmail = new AgentMailClient({ apiKey: AGENTMAIL_API_KEY });
const claude = new Anthropic({ apiKey: ANTHROPIC_API_KEY });

// --- per-reply tools (counterparty side) -------------------------------------

const REPLY_TOOLS = [
  {
    name: "record_offer",
    description: "Counterparty quoted a price/terms. Capture the structured fields.",
    input_schema: {
      type: "object" as const,
      required: ["price", "currency", "terms_summary", "meets_must_haves", "notes"],
      properties: {
        price: { type: "number" },
        currency: { type: "string" },
        terms_summary: { type: "string" },
        meets_must_haves: { type: "boolean" },
        notes: { type: "string" },
      },
    },
  },
  {
    name: "mark_declined",
    description: "Counterparty passed / can't fulfill.",
    input_schema: {
      type: "object" as const,
      required: ["reason"],
      properties: { reason: { type: "string" } },
    },
  },
  {
    name: "answer_question",
    description: "Counterparty needs clarification. Provide a short reply (under 60 words) without revealing buyer details or other offers.",
    input_schema: {
      type: "object" as const,
      required: ["reply_text"],
      properties: { reply_text: { type: "string" } },
    },
  },
];

// --- round summary tool ------------------------------------------------------

const SEND_ROUND_SUMMARY_TOOL = {
  name: "send_round_summary",
  description: "Compose the round summary email to the buyer with comparison table + recommendation.",
  input_schema: {
    type: "object" as const,
    required: ["comparison_table", "recommended_action", "target_hit_alert", "report_body"],
    properties: {
      comparison_table: { type: "string" },
      recommended_action: { type: "string" },
      target_hit_alert: { type: "boolean" },
      report_body: { type: "string" },
    },
  },
};

// --- buyer strategy tools ---------------------------------------------------

const BUYER_STRATEGY_TOOLS = [
  {
    name: "next_round",
    description: "Buyer chose to counter one or more counterparties.",
    input_schema: {
      type: "object" as const,
      required: ["counters"],
      properties: {
        counters: {
          type: "array",
          items: {
            type: "object" as const,
            required: ["counterparty_email", "anchor_price", "currency", "context_for_writer"],
            properties: {
              counterparty_email: { type: "string" },
              anchor_price: { type: "number" },
              currency: { type: "string" },
              context_for_writer: { type: "string" },
            },
          },
        },
      },
    },
  },
  {
    name: "walk_away_from",
    description: "Buyer wants to drop one or more counterparties.",
    input_schema: {
      type: "object" as const,
      required: ["counterparty_emails"],
      properties: {
        counterparty_emails: { type: "array", items: { type: "string" } },
      },
    },
  },
  {
    name: "escalate_for_human",
    description: "Buyer wants to ACCEPT. Agent never auto-accepts; this hands the deal back to the buyer.",
    input_schema: {
      type: "object" as const,
      required: ["counterparty_email", "summary"],
      properties: {
        counterparty_email: { type: "string" },
        summary: { type: "string" },
      },
    },
  },
];

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

function nowIso(): string {
  return new Date().toISOString();
}

async function getOrCreateInbox(): Promise<any> {
  const state = loadState();
  if (state.inboxId) {
    try { return await agentmail.inboxes.get(state.inboxId); }
    catch (e: any) { console.log(`(stale state, creating new inbox: ${e.message})`); }
  }
  const d = deal.load();
  const rawLabel = d?.what || "deal";
  const label = rawLabel.replace(/[^A-Za-z0-9 \-]+/g, "").trim().slice(0, 40) || "deal";
  const inbox = await agentmail.inboxes.create({
    username: INBOX_USERNAME,
    displayName: `Buyer's negotiator - ${label}`,
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

// --- writer (Claude composes outreach / counter) ----------------------------

async function writeOutreachBody(
  cp: deal.Counterparty,
  kind: "opening" | "counter" | "walk_away",
  extraContext: string = "",
): Promise<string> {
  const userPayload =
    `Email kind: ${kind}\n\n` +
    `Counterparty: ${cp.name ?? "?"} <${cp.email}>\n` +
    `Counterparty's previous offer (if any): ` +
    `${cp.current_offer ? JSON.stringify(cp.current_offer, null, 2) : "none"}\n\n` +
    `Extra context for this email: ${extraContext || "(none)"}\n\n` +
    `Compose the email body now.`;

  const response = await claude.messages.create({
    model: ANTHROPIC_MODEL,
    max_tokens: 400,
    system: buildWriterPrompt(),
    messages: [{ role: "user", content: userPayload }],
  });
  const block = response.content.find((b: any) => b.type === "text");
  return block && block.type === "text" ? block.text.trim() : "";
}

async function sendOpening(cp: deal.Counterparty, inbox: any): Promise<void> {
  console.log(`  ✉  opening → ${cp.email} (${cp.name})`);
  const body = await writeOutreachBody(cp, "opening");
  if (!body) { console.log("    ! empty body, skipping"); return; }

  const d = deal.load();
  const subject = `Inquiry — ${(d?.what || "item").slice(0, 60)}`;
  const sent = await agentmail.inboxes.messages.send(inbox.inboxId, {
    to: [cp.email], subject, text: body,
  });
  const threadId = sent.threadId ?? sent.messageId ?? "";
  deal.updateCounterparty(cp.email, {
    status: "contacted",
    thread_id: threadId,
    contacted_at: nowIso(),
  });
}

async function sendCounter(
  counterpartyEmail: string,
  anchorPrice: number,
  currency: string,
  extraContext: string,
  inbox: any,
): Promise<void> {
  const cp = deal.getCounterpartyByEmail(counterpartyEmail);
  if (!cp) { console.log(`  ! no counterparty ${counterpartyEmail}, skipping`); return; }
  console.log(`  ↪  counter → ${counterpartyEmail} at ${anchorPrice} ${currency}`);
  const extra = `Anchor at ${anchorPrice} ${currency}. ${extraContext}`.trim();
  const body = await writeOutreachBody(cp, "counter", extra);
  if (!body || !cp.thread_id) return;
  try {
    const thread = await agentmail.inboxes.threads.get(inbox.inboxId, cp.thread_id);
    const target = thread.messages?.[thread.messages.length - 1];
    if (target) {
      await agentmail.inboxes.messages.reply(inbox.inboxId, target.messageId, { text: body });
    }
    deal.updateCounterparty(counterpartyEmail, {
      status: "countered",
      last_counter_at: nowIso(),
      last_anchor: anchorPrice,
    });
  } catch (e: any) {
    console.log(`    ! counter send failed: ${e.message}`);
  }
}

async function sendWalkAway(counterpartyEmail: string, inbox: any): Promise<void> {
  const cp = deal.getCounterpartyByEmail(counterpartyEmail);
  if (!cp || !cp.thread_id) return;
  console.log(`  ✗ walking away from ${counterpartyEmail}`);
  const body = await writeOutreachBody(cp, "walk_away",
    "Polite close-out: we're going with another option, thank them for their time.");
  if (!body) return;
  try {
    const thread = await agentmail.inboxes.threads.get(inbox.inboxId, cp.thread_id);
    const target = thread.messages?.[thread.messages.length - 1];
    if (target) {
      await agentmail.inboxes.messages.reply(inbox.inboxId, target.messageId, { text: body });
    }
    deal.updateCounterparty(counterpartyEmail, { status: "walked" });
  } catch (e: any) {
    console.log(`    ! walk-away send failed: ${e.message}`);
  }
}

// --- reply handlers ---------------------------------------------------------

async function handleRecordOffer(args: any, message: any, inbox: any, cp: deal.Counterparty) {
  console.log(`  💰 offer from ${cp.email}: ${args.price} ${args.currency} (meets_must_haves=${args.meets_must_haves})`);
  deal.updateCounterparty(cp.email, {
    status: "offered",
    current_offer: {
      price: args.price,
      currency: args.currency,
      terms_summary: args.terms_summary || "",
      meets_must_haves: !!args.meets_must_haves,
      notes: args.notes || "",
      received_at: nowIso(),
    },
  });
}

async function handleMarkDeclined(args: any, message: any, inbox: any, cp: deal.Counterparty) {
  console.log(`  ✗ declined: ${cp.email} — ${args.reason || ""}`);
  deal.updateCounterparty(cp.email, { status: "declined", decline_reason: args.reason || "" });
}

async function handleAnswerQuestion(args: any, message: any, inbox: any, cp: deal.Counterparty) {
  const reply = (args.reply_text || "").trim();
  console.log(`  ❓ answering question from ${cp.email} (${reply.length} chars)`);
  if (reply) {
    await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, { text: reply });
  }
}

const REPLY_HANDLERS: Record<string, (args: any, message: any, inbox: any, cp: deal.Counterparty) => Promise<void>> = {
  record_offer: handleRecordOffer,
  mark_declined: handleMarkDeclined,
  answer_question: handleAnswerQuestion,
};

// --- buyer strategy handlers ------------------------------------------------

async function handleNextRound(args: any, message: any, inbox: any) {
  const counters = (args.counters || []) as any[];
  console.log(`  → buyer chose to counter ${counters.length} counterparty(ies)`);
  for (const c of counters) {
    await sendCounter(
      c.counterparty_email,
      c.anchor_price,
      c.currency || "USD",
      c.context_for_writer || "",
      inbox,
    );
  }
}

async function handleWalkAway(args: any, message: any, inbox: any) {
  const emails = (args.counterparty_emails || []) as string[];
  console.log(`  → buyer chose to walk from ${emails.length} counterparty(ies)`);
  for (const em of emails) {
    await sendWalkAway(em, inbox);
  }
}

async function handleEscalateForHuman(args: any, message: any, inbox: any) {
  const cpEmail = args.counterparty_email || "";
  const summary = args.summary || "";
  console.log(`  🤝 buyer wants to ACCEPT ${cpEmail}: ${summary}`);
  const body =
    `Acknowledged — handing the close to you.\n\n` +
    `You'll need to reach out to ${cpEmail} directly to finalize. The agent will not auto-accept on your behalf (this is a hard rule). All current threads remain open until you tell me to walk away from them.\n\n` +
    `Summary: ${summary}`;
  await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, { text: body });
  const d = deal.load();
  if (d) {
    d.buyer_accept_intent = d.buyer_accept_intent || [];
    d.buyer_accept_intent.push({ counterparty_email: cpEmail, summary, at: nowIso() });
    deal.save(d);
  }
}

const BUYER_STRATEGY_HANDLERS: Record<string, (args: any, message: any, inbox: any) => Promise<void>> = {
  next_round: handleNextRound,
  walk_away_from: handleWalkAway,
  escalate_for_human: handleEscalateForHuman,
};

// --- core processing --------------------------------------------------------

async function processCounterpartyReply(message: any, inbox: any, cp: deal.Counterparty) {
  console.log(`  → counterparty reply from ${cp.email}`);
  const thread = await agentmail.inboxes.threads.get(inbox.inboxId, message.threadId);
  const latest = thread.messages?.[thread.messages.length - 1];
  const body = ((latest?.extractedText ?? latest?.text) || "").trim();

  const userPayload =
    `Counterparty: ${cp.name ?? "?"} <${cp.email}>\n` +
    `Their previous offer (if any): ${JSON.stringify(cp.current_offer || {})}\n\n` +
    `--- Their reply ---\n${body.slice(0, 4000)}`;

  const response = await claude.messages.create({
    model: ANTHROPIC_MODEL, max_tokens: 1024,
    system: buildReplyClassifierPrompt(),
    tools: REPLY_TOOLS, tool_choice: { type: "any" },
    messages: [{ role: "user", content: userPayload }],
  });

  let handled = false;
  for (const block of response.content) {
    if (block.type === "tool_use" && REPLY_HANDLERS[block.name]) {
      try {
        await REPLY_HANDLERS[block.name](block.input, message, inbox, cp);
        handled = true;
        await markRead(inbox.inboxId, message.messageId, ["counterparty", block.name]);
      } catch (e: any) {
        console.log(`  ! handler ${block.name} failed: ${e.message}`);
      }
    }
  }
  if (!handled) await markRead(inbox.inboxId, message.messageId);
}

async function processBuyerReply(message: any, inbox: any) {
  console.log(`  → buyer reply (strategy)`);
  const thread = await agentmail.inboxes.threads.get(inbox.inboxId, message.threadId);
  const latest = thread.messages?.[thread.messages.length - 1];
  const body = ((latest?.extractedText ?? latest?.text) || "").trim();

  const d = deal.load();
  const snapshot = JSON.stringify(
    (d?.counterparties || []).map((cp) => ({
      email: cp.email, name: cp.name, status: cp.status, current_offer: cp.current_offer,
    })), null, 2,
  );

  const system =
    "You translate the buyer's strategy reply into structured tool calls. " +
    "The buyer is responding to your last round-summary. They might say things like " +
    "'counter A with $34k, walk B' or 'accept C's offer' or 'wait for D to reply first'.\n\n" +
    "Available tools:\n" +
    "- next_round(counters[]) — send counter offer(s) to one or more counterparties\n" +
    "- walk_away_from(counterparty_emails[]) — close out one or more counterparties\n" +
    "- escalate_for_human(counterparty_email, summary) — buyer wants to ACCEPT; we hand it back to them\n\n" +
    "If the buyer says 'wait' or 'hold' or 'let me think', call no tools.\n" +
    "Always use exact counterparty emails from the deal state.";

  const userPayload =
    `Current deal state:\n${snapshot}\n\n` +
    `--- Buyer's reply ---\n${body.slice(0, 4000)}`;

  const response = await claude.messages.create({
    model: ANTHROPIC_MODEL, max_tokens: 2048,
    system, tools: BUYER_STRATEGY_TOOLS, tool_choice: { type: "auto" },
    messages: [{ role: "user", content: userPayload }],
  });

  let handled = false;
  for (const block of response.content) {
    if (block.type === "tool_use" && BUYER_STRATEGY_HANDLERS[block.name]) {
      try {
        await BUYER_STRATEGY_HANDLERS[block.name](block.input, message, inbox);
        handled = true;
        await markRead(inbox.inboxId, message.messageId, ["buyer", block.name]);
      } catch (e: any) {
        console.log(`  ! buyer-handler ${block.name} failed: ${e.message}`);
      }
    }
  }
  if (!handled) {
    console.log("  → no actionable strategy in buyer's reply, idling");
    await markRead(inbox.inboxId, message.messageId, ["buyer", "idle"]);
  }
}

// --- round summary ----------------------------------------------------------

async function maybeSendRoundSummary(inbox: any) {
  const state = loadState();
  if ((state.round_summary_sent_for_round ?? 0) >= (state.current_round ?? 1)) return;

  const d = deal.load();
  if (!d || !d.counterparties.length) return;
  if (!deal.allReplied(d)) return;

  console.log(`\n📊 Composing round ${state.current_round ?? 1} summary…`);

  const snapshot = d.counterparties.map((cp) => ({
    email: cp.email, name: cp.name, status: cp.status, current_offer: cp.current_offer,
  }));
  const userPayload =
    `Round ${state.current_round ?? 1} state:\n` +
    `${JSON.stringify(snapshot, null, 2)}\n\n` +
    `Compose the round summary now.`;

  const response = await claude.messages.create({
    model: ANTHROPIC_MODEL, max_tokens: 2048,
    system: buildRoundSummaryPrompt(),
    tools: [SEND_ROUND_SUMMARY_TOOL], tool_choice: { type: "any" },
    messages: [{ role: "user", content: userPayload }],
  });

  for (const block of response.content) {
    if (block.type === "tool_use" && block.name === "send_round_summary") {
      const args = block.input as any;
      const subjectPrefix = args.target_hit_alert ? "[TARGET HIT] " : "";
      const subject = `${subjectPrefix}Negotiation update — round ${state.current_round ?? 1} summary`;

      const buyerThreadId = state.buyer_thread_id;
      try {
        if (buyerThreadId) {
          const thread = await agentmail.inboxes.threads.get(inbox.inboxId, buyerThreadId);
          const buyerMsgs = (thread.messages || []).filter((m: any) => senderEmail(m) === BUYER_EMAIL_LC);
          const target = buyerMsgs[buyerMsgs.length - 1];
          if (target) {
            await agentmail.inboxes.messages.reply(inbox.inboxId, target.messageId, { text: args.report_body });
          } else {
            await agentmail.inboxes.messages.send(inbox.inboxId, {
              to: [BUYER_EMAIL!], subject, text: args.report_body,
            });
          }
        } else {
          const sent = await agentmail.inboxes.messages.send(inbox.inboxId, {
            to: [BUYER_EMAIL!], subject, text: args.report_body,
          });
          state.buyer_thread_id = sent.threadId ?? sent.messageId ?? "";
        }
      } catch (e: any) {
        console.log(`  ! sending round summary failed: ${e.message}`);
        return;
      }

      state.round_summary_sent_for_round = state.current_round ?? 1;
      state.current_round = (state.current_round ?? 1) + 1;
      saveState(state);
      const alert = args.target_hit_alert ? " [TARGET HIT]" : "";
      console.log(`  ✅ round summary sent to ${BUYER_EMAIL}${alert}`);
      return;
    }
  }
}

// --- main loop --------------------------------------------------------------

async function main() {
  const d = deal.load();
  if (!d) {
    console.error("ERROR: deal.json not found or empty. Run `cp deal.example.json deal.json` and edit it.");
    process.exit(1);
  }

  const inbox = await getOrCreateInbox();
  console.log(`\n📬 Negotiation agent live at: ${inbox.email}`);
  console.log(`   Buyer: ${BUYER_EMAIL}`);
  console.log(`   Negotiating: ${d.what}`);
  console.log(`   Ideal: ${d.ideal_price} ${d.currency}, max: ${d.max_price} ${d.currency}`);
  console.log(`   Counterparties: ${d.counterparties.length}`);
  console.log(`   Polling every ${POLL_MS / 1000}s. Ctrl-C to stop.\n`);

  const state = loadState();
  if (!state.current_round) {
    state.current_round = 1;
    saveState(state);
  }

  const seen = new Set<string>();
  while (true) {
    try {
      // 1) Send opening to any queued counterparties
      for (const cp of deal.queuedCounterparties()) {
        try { await sendOpening(cp, inbox); }
        catch (e: any) { console.log(`  ! opening failed for ${cp.email}: ${e.message}`); }
      }

      // 2) Process new replies
      const resp = await agentmail.inboxes.messages.list(inbox.inboxId, { labels: ["unread"] });
      const newMsgs = (resp.messages || []).filter((m: any) => !seen.has(m.messageId));
      for (const m of newMsgs) {
        seen.add(m.messageId);
        if (senderEmail(m) === inbox.email.toLowerCase()) continue;

        const cp = deal.getCounterpartyByThread(m.threadId);
        if (cp) {
          console.log(`\n📩 from ${senderEmail(m)} (counterparty ${cp.name})`);
          try { await processCounterpartyReply(m, inbox, cp); }
          catch (e: any) { console.log(`  ! cp-reply error: ${e.message}`); }
        } else if (senderEmail(m) === BUYER_EMAIL_LC) {
          console.log(`\n📩 from ${senderEmail(m)} (buyer strategy)`);
          try { await processBuyerReply(m, inbox); }
          catch (e: any) { console.log(`  ! buyer-reply error: ${e.message}`); }
        } else {
          console.log(`\n📩 unknown sender ${senderEmail(m)}, skipping`);
          await markRead(inbox.inboxId, m.messageId, ["unknown"]);
        }
      }

      // 3) Maybe send round summary
      await maybeSendRoundSummary(inbox);
    } catch (e: any) {
      console.log(`poll error: ${e.message}`);
    }
    await new Promise((r) => setTimeout(r, POLL_MS));
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
