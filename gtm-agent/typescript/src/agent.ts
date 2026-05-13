/**
 * AgentMail GTM Agent — TypeScript.
 */

import "dotenv/config";
import * as fs from "node:fs";
import { AgentMailClient } from "agentmail";
import Anthropic from "@anthropic-ai/sdk";
import * as prospects from "./prospects.js";
import { buildClassifierPrompt, buildWriterPrompt } from "./prompt.js";

// --- config ------------------------------------------------------------------

const {
  AGENTMAIL_API_KEY,
  ANTHROPIC_API_KEY,
  SENDER_NAME = "Sender",
  SENDER_COMPANY = "Company",
  SALES_EMAIL,
  ANTHROPIC_MODEL = "claude-sonnet-4-6",
  POLL_INTERVAL_SECONDS = "30",
  FOLLOWUP_AFTER_HOURS = "96",
  INBOX_USERNAME,
} = process.env;

if (!AGENTMAIL_API_KEY) throw new Error("AGENTMAIL_API_KEY required");
if (!ANTHROPIC_API_KEY) throw new Error("ANTHROPIC_API_KEY required");
if (!SALES_EMAIL) throw new Error("SALES_EMAIL required");

const POLL_MS = Number(POLL_INTERVAL_SECONDS) * 1000;
const FOLLOWUP_AFTER = Number(FOLLOWUP_AFTER_HOURS);
const STATE_FILE = ".agent_state.json";

// --- clients -----------------------------------------------------------------

const agentmail = new AgentMailClient({ apiKey: AGENTMAIL_API_KEY });
const claude = new Anthropic({ apiKey: ANTHROPIC_API_KEY });

// --- classifier tools --------------------------------------------------------

const CLASSIFIER_TOOLS = [
  {
    name: "mark_interested",
    description:
      "Reply shows positive interest. Sends an immediate warm acknowledgment back to the prospect in the same thread (keeps them engaged while the sales team picks up), then forwards the original reply to the sales team with handoff context.",
    input_schema: {
      type: "object" as const,
      required: ["prospect_acknowledgment", "summary", "handoff_note"],
      properties: {
        prospect_acknowledgment: {
          type: "string",
          description: "2-3 sentence warm reply to the prospect IMMEDIATELY in the same thread. Reference what they said specifically. CRITICAL: NEVER invent a specific sales-rep name — refer to 'our team' or 'our sales team' generically (naming a person risks hallucinating someone who doesn't exist). Do NOT promise times/pricing — sales owns that.",
        },
        summary: { type: "string", description: "1-2 sentence summary of the prospect's signal." },
        handoff_note: { type: "string", description: "Cover note for the sales team — what to know + suggested next step." },
      },
    },
  },
  {
    name: "mark_not_interested",
    description: "Reply is a decline. Stop touching this prospect. We do NOT reply to declines.",
    input_schema: {
      type: "object" as const,
      required: ["reason"],
      properties: { reason: { type: "string" } },
    },
  },
  {
    name: "mark_ooo",
    description: "Reply is an out-of-office / vacation auto-reply. Pause; don't follow up until they're back.",
    input_schema: {
      type: "object" as const,
      required: ["return_date_or_note"],
      properties: { return_date_or_note: { type: "string" } },
    },
  },
  {
    name: "mark_question",
    description: "Prospect is asking a clarifying question without taking a clear side. Provide a suggested response we'll send in-thread.",
    input_schema: {
      type: "object" as const,
      required: ["suggested_response"],
      properties: { suggested_response: { type: "string" } },
    },
  },
];

// --- helpers -----------------------------------------------------------------

function senderEmail(message: any): string {
  const raw = String(message?.from ?? message?.from_ ?? "");
  const match = raw.match(/<([^>]+)>/);
  return (match ? match[1] : raw).trim().toLowerCase();
}

function nowIso(): string {
  return new Date().toISOString();
}

function loadState(): Record<string, any> {
  if (!fs.existsSync(STATE_FILE)) return {};
  try { return JSON.parse(fs.readFileSync(STATE_FILE, "utf8")); }
  catch { return {}; }
}

function saveState(state: Record<string, any>): void {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

async function getOrCreateInbox(): Promise<any> {
  const state = loadState();
  if (state.inboxId) {
    try { return await agentmail.inboxes.get(state.inboxId); }
    catch (e: any) { console.log(`(stale state, creating new inbox: ${e.message})`); }
  }
  const inbox = await agentmail.inboxes.create({
    username: INBOX_USERNAME,
    displayName: `${SENDER_NAME} - ${SENDER_COMPANY}`,
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

function subjectFromHook(hook: string, company: string): string {
  const h = (hook || "").trim().replace(/\.$/, "");
  if (!h) return company ? `Quick question about ${company}` : "Quick question";
  return h.length <= 60 ? h : h.slice(0, 57) + "…";
}

// --- outreach (writing + sending) -------------------------------------------

async function writeEmailBody(prospect: prospects.Prospect, touch: "first" | "follow-up"): Promise<string> {
  const userPayload =
    `Touch: ${touch}\n\n` +
    `Prospect:\n  Name: ${prospect.name}\n  Role: ${prospect.role}\n` +
    `  Company: ${prospect.company}\n  Hook (specific signal to lead with): ${prospect.hook}\n`;
  const response = await claude.messages.create({
    model: ANTHROPIC_MODEL,
    max_tokens: 400,
    system: buildWriterPrompt(),
    messages: [{ role: "user", content: userPayload }],
  });
  const text = response.content.find((b: any) => b.type === "text");
  return text && text.type === "text" ? text.text.trim() : "";
}

async function sendFirstTouch(prospect: prospects.Prospect, inbox: any): Promise<void> {
  console.log(`  ✉  first touch → ${prospect.email} (${prospect.name}, ${prospect.company})`);
  const body = await writeEmailBody(prospect, "first");
  if (!body) { console.log("    ! empty body, skipping"); return; }
  const subject = subjectFromHook(prospect.hook, prospect.company);

  const sent = await agentmail.inboxes.messages.send(inbox.inboxId, {
    to: [prospect.email], subject, text: body,
  });
  const threadId = sent.threadId ?? sent.messageId ?? "";

  prospects.updateProspect(prospect.email, {
    status: "first_touch_sent",
    first_touch_at: nowIso(),
    thread_id: threadId,
  });
  prospects.logAction({
    action: "first_touch", prospect_email: prospect.email,
    thread_id: threadId, note: body.slice(0, 200),
  });
}

async function sendFollowup(prospect: prospects.Prospect, inbox: any): Promise<void> {
  console.log(`  ↪  follow-up → ${prospect.email}`);
  const body = await writeEmailBody(prospect, "follow-up");
  if (!body) return;

  if (prospect.thread_id) {
    try {
      const thread = await agentmail.inboxes.threads.get(inbox.inboxId, prospect.thread_id);
      const ourMsgs = (thread.messages || []).filter(
        (m: any) => senderEmail(m) === inbox.email.toLowerCase(),
      );
      const target = ourMsgs[ourMsgs.length - 1] || (thread.messages?.[thread.messages.length - 1]);
      if (target) {
        await agentmail.inboxes.messages.reply(inbox.inboxId, target.messageId, { text: body });
      }
    } catch (e: any) {
      console.log(`    ! reply failed, falling back to new send: ${e.message}`);
      await agentmail.inboxes.messages.send(inbox.inboxId, {
        to: [prospect.email],
        subject: `Re: ${subjectFromHook(prospect.hook, prospect.company)}`,
        text: body,
      });
    }
  }

  prospects.updateProspect(prospect.email, {
    status: "followed_up", followup_at: nowIso(),
  });
  prospects.logAction({
    action: "follow_up", prospect_email: prospect.email,
    thread_id: prospect.thread_id, note: body.slice(0, 200),
  });
}

// --- classifier handlers -----------------------------------------------------

async function handleMarkInterested(args: any, message: any, inbox: any, prospect: prospects.Prospect) {
  const summary = (args.summary || "").trim();
  const note = (args.handoff_note || "").trim();
  const ack = (args.prospect_acknowledgment || "").trim();
  console.log(`  🎯 INTERESTED: ${summary}`);

  // 1) Warm ack to prospect FIRST
  if (ack) {
    try {
      await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, { text: ack });
      console.log(`  💬 warm ack sent to prospect (${ack.length} chars)`);
    } catch (e: any) {
      console.log(`    ! warm ack failed: ${e.message}`);
    }
  }

  // 2) Forward to sales
  try {
    await agentmail.inboxes.messages.forward(inbox.inboxId, message.messageId, {
      to: [SALES_EMAIL!],
      text:
        `[INTERESTED LEAD]\n\n` +
        `Prospect: ${prospect.name} <${prospect.email}> (${prospect.role} at ${prospect.company})\n\n` +
        `Summary: ${summary}\n\n` +
        `Suggested next step: ${note}\n\n` +
        `---\n` +
        `Note: I've already sent a warm acknowledgment to the prospect in-thread — they're expecting your follow-up shortly. The original reply is quoted below.`,
    });
  } catch (e: any) {
    console.log(`    ! handoff forward failed: ${e.message}`);
  }

  prospects.updateProspect(prospect.email, {
    status: "handed_off", replied_at: nowIso(), classification: "interested",
  });
  prospects.logAction({
    action: "handed_off", prospect_email: prospect.email,
    classification: "interested", thread_id: message.threadId, note: summary,
  });
}

async function handleMarkNotInterested(args: any, message: any, inbox: any, prospect: prospects.Prospect) {
  const reason = (args.reason || "").trim();
  console.log(`  ✗ NOT INTERESTED: ${reason}`);
  prospects.updateProspect(prospect.email, {
    status: "closed_lost", replied_at: nowIso(), classification: "not_interested",
  });
  prospects.logAction({
    action: "closed_lost", prospect_email: prospect.email,
    classification: "not_interested", thread_id: message.threadId, note: reason,
  });
}

async function handleMarkOoo(args: any, message: any, inbox: any, prospect: prospects.Prospect) {
  const note = (args.return_date_or_note || "").trim();
  console.log(`  🏖  OOO: ${note}`);
  prospects.updateProspect(prospect.email, { status: "paused_ooo", classification: "ooo" });
  prospects.logAction({
    action: "paused_ooo", prospect_email: prospect.email,
    classification: "ooo", thread_id: message.threadId, note,
  });
}

async function handleMarkQuestion(args: any, message: any, inbox: any, prospect: prospects.Prospect) {
  const suggested = (args.suggested_response || "").trim();
  console.log(`  ❓ QUESTION: replying with ${suggested.length} chars`);
  if (!suggested) return;
  await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, { text: suggested });
  prospects.updateProspect(prospect.email, {
    status: "q_and_a", replied_at: nowIso(), classification: "question",
  });
  prospects.logAction({
    action: "answered_question", prospect_email: prospect.email,
    classification: "question", thread_id: message.threadId, note: suggested.slice(0, 200),
  });
}

const CLASSIFIER_HANDLERS: Record<string, (args: any, message: any, inbox: any, prospect: prospects.Prospect) => Promise<void>> = {
  mark_interested: handleMarkInterested,
  mark_not_interested: handleMarkNotInterested,
  mark_ooo: handleMarkOoo,
  mark_question: handleMarkQuestion,
};

// --- core processing ---------------------------------------------------------

async function processReply(message: any, inbox: any) {
  const prospect = prospects.findByThread(message.threadId);
  if (!prospect) {
    console.log("  ! reply on a thread with no tracked prospect, skipping");
    await markRead(inbox.inboxId, message.messageId, ["unknown"]);
    return;
  }

  console.log(`  → reply from ${prospect.email} (${prospect.name}, ${prospect.company})`);
  const thread = await agentmail.inboxes.threads.get(inbox.inboxId, message.threadId);
  const latest = (thread.messages || [])[thread.messages!.length - 1];
  const body = ((latest.extractedText ?? latest.text) || "").trim();

  const userPayload =
    `Original outreach to ${prospect.name} (${prospect.role} at ${prospect.company}).\n` +
    `Hook used: ${prospect.hook}\n\n` +
    `--- Their reply ---\n${body.slice(0, 4000)}`;

  console.log(`  → asking Claude to classify (model=${ANTHROPIC_MODEL})`);
  const response = await claude.messages.create({
    model: ANTHROPIC_MODEL, max_tokens: 1024,
    system: buildClassifierPrompt(),
    tools: CLASSIFIER_TOOLS, tool_choice: { type: "any" },
    messages: [{ role: "user", content: userPayload }],
  });

  let handled = false;
  for (const block of response.content) {
    if (block.type === "tool_use" && CLASSIFIER_HANDLERS[block.name]) {
      try {
        await CLASSIFIER_HANDLERS[block.name](block.input, message, inbox, prospect);
        handled = true;
        await markRead(inbox.inboxId, message.messageId, [block.name.replace("mark_", "")]);
      } catch (e: any) {
        console.log(`  ! handler ${block.name} failed: ${e.message}`);
      }
    }
  }

  if (!handled) {
    console.log("  ! Claude did not call any tool");
    await markRead(inbox.inboxId, message.messageId);
  }
}

// --- main loop ---------------------------------------------------------------

async function main() {
  const inbox = await getOrCreateInbox();
  console.log(`\n📬 GTM agent live at: ${inbox.email}`);
  console.log(`   Sender: ${SENDER_NAME}, ${SENDER_COMPANY}`);
  console.log(`   Sales team handoff: ${SALES_EMAIL}`);
  console.log(`   Follow-up cadence: ${FOLLOWUP_AFTER}h after first touch`);
  console.log(`   Polling every ${POLL_MS / 1000}s. Ctrl-C to stop.\n`);

  const seen = new Set<string>();
  while (true) {
    try {
      // 1) First-touch queued prospects
      for (const p of prospects.queuedProspects()) {
        try { await sendFirstTouch(p, inbox); }
        catch (e: any) { console.log(`  ! first-touch failed for ${p.email}: ${e.message}`); }
      }
      // 2) Follow-ups for stale prospects
      for (const p of prospects.followupsDue(FOLLOWUP_AFTER)) {
        try { await sendFollowup(p, inbox); }
        catch (e: any) { console.log(`  ! follow-up failed for ${p.email}: ${e.message}`); }
      }
      // 3) Process replies
      const resp = await agentmail.inboxes.messages.list(inbox.inboxId, { labels: ["unread"] });
      const newMsgs = (resp.messages || []).filter((m: any) => !seen.has(m.messageId));
      for (const m of newMsgs) {
        seen.add(m.messageId);
        if (senderEmail(m) === inbox.email.toLowerCase()) continue;
        console.log(`\n📩 from ${senderEmail(m)}: ${(m.subject || "(no subject)").slice(0, 60)}`);
        try { await processReply(m, inbox); }
        catch (e: any) { console.log(`  ! error processing reply: ${e.message}`); }
      }
    } catch (e: any) {
      console.log(`poll error: ${e.message}`);
    }
    await new Promise((r) => setTimeout(r, POLL_MS));
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
