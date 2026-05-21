/**
 * AgentMail Support Agent — triage, respond, escalate, follow up, close.
 *
 * Workflow:
 *   1. Create (or reuse) an AgentMail inbox.
 *   2. Poll for new mail every POLL_INTERVAL seconds.
 *   3. For each new email: ask Claude to call exactly one of respond / escalate
 *      / close_ticket. Optionally use web_search across HELP_CENTER_URL first.
 *      Tag the ticket with the classification.
 *   4. Once per cycle, scan tracked tickets and send a 48h follow-up to anyone
 *      waiting on us with no recent update.
 *   5. Append every action to tickets.csv for the support manager.
 *
 * Run:
 *     npm install
 *     cp .env.example .env   # then fill in your keys
 *     npm start
 */

import "dotenv/config";
import * as fs from "node:fs";
import { AgentMailClient } from "agentmail";
import Anthropic from "@anthropic-ai/sdk";
import { buildSystemPrompt } from "./prompt.js";
import { logTicket } from "./ticketLog.js";

// --- config ------------------------------------------------------------------

const {
  AGENTMAIL_API_KEY,
  ANTHROPIC_API_KEY,
  PRODUCT_NAME = "the product",
  AGENT_NAME = "Sam",
  ESCALATION_EMAIL,
  HELP_CENTER_URL = "",
  ANTHROPIC_MODEL = "claude-sonnet-4-6",
  POLL_INTERVAL_SECONDS = "10",
  FOLLOWUP_AFTER_HOURS = "48",
  FOLLOWUP_COOLDOWN_HOURS = "24",
  INBOX_USERNAME,
} = process.env;

if (!AGENTMAIL_API_KEY) throw new Error("AGENTMAIL_API_KEY required");
if (!ANTHROPIC_API_KEY) throw new Error("ANTHROPIC_API_KEY required");
if (!ESCALATION_EMAIL) throw new Error("ESCALATION_EMAIL required");

const POLL_MS = Number(POLL_INTERVAL_SECONDS) * 1000;
const FOLLOWUP_AFTER_MS = Number(FOLLOWUP_AFTER_HOURS) * 60 * 60 * 1000;
const FOLLOWUP_COOLDOWN_MS = Number(FOLLOWUP_COOLDOWN_HOURS) * 60 * 60 * 1000;
const STATE_FILE = ".agent_state.json";

const HELP_CENTER_DOMAIN = (() => {
  if (!HELP_CENTER_URL) return "";
  try {
    return new URL(HELP_CENTER_URL).hostname;
  } catch {
    return "";
  }
})();

const CLASSIFICATIONS = ["billing", "bug", "feature_request", "general", "urgent"];

// --- clients -----------------------------------------------------------------

const agentmail = new AgentMailClient({ apiKey: AGENTMAIL_API_KEY });
const claude = new Anthropic({ apiKey: ANTHROPIC_API_KEY });

// --- Claude tools ------------------------------------------------------------

function buildTools(): any[] {
  const tools: any[] = [];
  if (HELP_CENTER_DOMAIN) {
    tools.push({
      type: "web_search_20250305" as const,
      name: "web_search" as const,
      allowed_domains: [HELP_CENTER_DOMAIN],
      max_uses: 3,
    });
  }
  tools.push(
    {
      name: "respond",
      description:
        "Reply to the customer with the answer. Use when the KB or web search has the info.",
      input_schema: {
        type: "object" as const,
        required: ["text", "classification"],
        properties: {
          text: { type: "string", description: "The reply body, signed as instructed." },
          classification: { type: "string", enum: CLASSIFICATIONS },
        },
      },
    },
    {
      name: "escalate",
      description:
        "Forward to the human team when you can't answer or human approval is needed.",
      input_schema: {
        type: "object" as const,
        required: ["reason", "classification"],
        properties: {
          reason: { type: "string", description: "One-sentence summary for the escalation team." },
          classification: { type: "string", enum: CLASSIFICATIONS },
        },
      },
    },
    {
      name: "close_ticket",
      description:
        "Send a brief friendly close when the customer signals they're done.",
      input_schema: {
        type: "object" as const,
        required: ["message", "classification"],
        properties: {
          message: { type: "string", description: "Short closing message, signed." },
          classification: { type: "string", enum: CLASSIFICATIONS },
        },
      },
    },
  );
  return tools;
}

const TOOLS = buildTools();

// --- state -------------------------------------------------------------------

function loadState(): Record<string, any> {
  if (!fs.existsSync(STATE_FILE)) return {};
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
  } catch {
    return {};
  }
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
    try {
      return await agentmail.inboxes.get(state.inboxId);
    } catch (e: any) {
      console.log(`(stale state, creating new inbox: ${e.message})`);
    }
  }
  const inbox = await agentmail.inboxes.create({
    username: INBOX_USERNAME,
    displayName: `${PRODUCT_NAME} support`,
  });
  state.inboxId = inbox.inboxId;
  state.email = inbox.email;
  saveState(state);
  return inbox;
}

function threadToMessages(thread: any, ourEmail: string) {
  const ours = ourEmail.toLowerCase();
  const msgs: { role: "user" | "assistant"; content: string }[] = [];

  for (const m of thread.messages || []) {
    const role: "user" | "assistant" =
      senderEmail(m) === ours ? "assistant" : "user";
    const body = ((m.extractedText ?? m.text) || "").trim();
    if (body) msgs.push({ role, content: body });
  }

  while (msgs.length && msgs[0].role === "assistant") msgs.shift();

  const collapsed: typeof msgs = [];
  for (const m of msgs) {
    const last = collapsed[collapsed.length - 1];
    if (last && last.role === m.role) last.content += "\n\n" + m.content;
    else collapsed.push(m);
  }
  return collapsed;
}

async function markRead(
  inboxId: string,
  messageId: string,
  addLabels?: string[],
) {
  try {
    await agentmail.inboxes.messages.update(inboxId, messageId, {
      removeLabels: ["unread"],
      addLabels,
    });
  } catch (e: any) {
    console.log(`  ! couldn't mark read: ${e.message}`);
  }
}

// --- tool handlers -----------------------------------------------------------

async function handleRespond(args: any, message: any, inbox: any) {
  const text = String(args.text || "").trim();
  const classification = String(args.classification || "general");
  console.log(`  💬 respond (${classification}, ${text.length} chars)`);
  await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
    text,
  });
  await markRead(inbox.inboxId, message.messageId, [classification, "responded"]);
  logTicket({
    action: "responded",
    classification,
    sender: senderEmail(message),
    subject: message.subject || "",
    messageId: message.messageId,
    threadId: message.threadId,
    note: text.slice(0, 200),
  });
}

async function handleEscalate(args: any, message: any, inbox: any) {
  const reason = String(args.reason || "Unable to answer.").trim();
  const classification = String(args.classification || "general");
  console.log(`  ⚠️  escalate (${classification}): ${reason}`);
  try {
    await agentmail.inboxes.messages.forward(inbox.inboxId, message.messageId, {
      to: [ESCALATION_EMAIL!],
      text: `[${classification.toUpperCase()}] ${reason}`,
    });
  } catch (e: any) {
    console.log(`  ! escalation forward failed: ${e.message}`);
  }

  const ack =
    "Thanks for reaching out — I'm looping in our team to take a closer look at this. We'll be in touch shortly.";
  await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
    text: ack,
  });
  await markRead(inbox.inboxId, message.messageId, [
    classification,
    "escalated",
    "awaiting_team",
  ]);

  // Track for 48h follow-up
  const state = loadState();
  state.escalations = state.escalations || {};
  state.escalations[message.threadId] = {
    escalatedAt: new Date().toISOString(),
    lastFollowupAt: null,
    classification,
    subject: message.subject || "",
    sender: senderEmail(message),
    messageId: message.messageId,
  };
  saveState(state);

  logTicket({
    action: "escalated",
    classification,
    sender: senderEmail(message),
    subject: message.subject || "",
    messageId: message.messageId,
    threadId: message.threadId,
    note: reason,
  });
}

async function handleCloseTicket(args: any, message: any, inbox: any) {
  const text = String(
    args.message || "Glad I could help — closing this out.",
  ).trim();
  const classification = String(args.classification || "general");
  console.log(`  ✅ close_ticket (${classification})`);
  await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
    text,
  });
  await markRead(inbox.inboxId, message.messageId, [classification, "closed"]);

  const state = loadState();
  if (state.escalations) delete state.escalations[message.threadId];
  saveState(state);

  logTicket({
    action: "closed",
    classification,
    sender: senderEmail(message),
    subject: message.subject || "",
    messageId: message.messageId,
    threadId: message.threadId,
    note: text.slice(0, 200),
  });
}

const TOOL_HANDLERS: Record<
  string,
  (args: any, message: any, inbox: any) => Promise<void>
> = {
  respond: handleRespond,
  escalate: handleEscalate,
  close_ticket: handleCloseTicket,
};

// --- core processing ---------------------------------------------------------

async function processMessage(message: any, inbox: any) {
  console.log(`  → fetching thread ${message.threadId}`);
  const thread = await agentmail.inboxes.threads.get(
    inbox.inboxId,
    message.threadId,
  );

  const last = thread.messages?.[thread.messages.length - 1];
  if (
    last &&
    senderEmail(last) === inbox.email.toLowerCase() &&
    message.messageId !== last.messageId
  ) {
    console.log("  → thread already replied; skipping");
    await markRead(inbox.inboxId, message.messageId);
    return;
  }

  const conversation = threadToMessages(thread, inbox.email);
  if (
    !conversation.length ||
    conversation[conversation.length - 1].role !== "user"
  ) {
    console.log("  ! no user content to act on");
    await markRead(inbox.inboxId, message.messageId);
    return;
  }

  const system = buildSystemPrompt({ inboxEmail: inbox.email });
  console.log(
    `  → asking Claude (model=${ANTHROPIC_MODEL}${HELP_CENTER_DOMAIN ? `, web_search → ${HELP_CENTER_DOMAIN}` : ""})`,
  );
  const response = await claude.messages.create({
    model: ANTHROPIC_MODEL,
    max_tokens: 2048,
    system,
    tools: TOOLS,
    messages: conversation,
  });

  let handled = false;
  for (const block of response.content) {
    if (block.type === "tool_use" && TOOL_HANDLERS[block.name]) {
      try {
        await TOOL_HANDLERS[block.name](block.input, message, inbox);
        handled = true;
      } catch (e: any) {
        console.log(`  ! tool handler ${block.name} failed: ${e.message}`);
      }
    }
  }

  if (!handled) {
    console.log("  ! Claude did not call any action tool");
    await markRead(inbox.inboxId, message.messageId);
  }
}

// --- 48h follow-up -----------------------------------------------------------

async function maybeSendFollowups(inbox: any) {
  const state = loadState();
  const escalations = state.escalations || {};
  if (!Object.keys(escalations).length) return;

  const now = Date.now();
  let sent = 0;

  for (const [threadId, info] of Object.entries(escalations) as [string, any][]) {
    try {
      const escalatedAt = new Date(info.escalatedAt).getTime();
      const lastFu = info.lastFollowupAt ? new Date(info.lastFollowupAt).getTime() : null;

      if (now - escalatedAt < FOLLOWUP_AFTER_MS) continue;
      if (lastFu && now - lastFu < FOLLOWUP_COOLDOWN_MS) continue;

      console.log(`  📨 sending 48h follow-up on thread ${threadId.slice(0, 8)}...`);
      await agentmail.inboxes.messages.reply(inbox.inboxId, info.messageId, {
        text:
          "Quick update — wanted to let you know this is still on our team's radar. " +
          "We're working through it and will follow up as soon as we have an answer. " +
          "Apologies for the wait.\n\n" +
          `${AGENT_NAME}, Support Team`,
      });

      info.lastFollowupAt = new Date().toISOString();
      sent++;

      logTicket({
        action: "followed_up",
        classification: info.classification || "general",
        sender: info.sender || "",
        subject: info.subject || "",
        messageId: info.messageId,
        threadId,
        note: `Follow-up sent ${FOLLOWUP_AFTER_HOURS}h after escalation`,
      });
    } catch (e: any) {
      console.log(`  ! follow-up failed for ${threadId}: ${e.message}`);
    }
  }

  if (sent) saveState(state);
}

// --- main loop ---------------------------------------------------------------

async function main() {
  const inbox = await getOrCreateInbox();
  console.log(`\n📬 Support agent live at: ${inbox.email}`);
  if (HELP_CENTER_DOMAIN) console.log(`   Web search: ${HELP_CENTER_URL}`);
  console.log(`   Escalating to: ${ESCALATION_EMAIL}`);
  console.log(
    `   Follow-up: ${FOLLOWUP_AFTER_HOURS}h after escalation, max once per ${FOLLOWUP_COOLDOWN_HOURS}h`,
  );
  console.log(`   Polling every ${POLL_MS / 1000}s. Ctrl-C to stop.\n`);

  const seen = new Set<string>();
  while (true) {
    try {
      const resp = await agentmail.inboxes.messages.list(inbox.inboxId, {
        labels: ["unread"],
      });
      const newMsgs = (resp.messages || []).filter(
        (m: any) => !seen.has(m.messageId),
      );
      for (const m of newMsgs) {
        seen.add(m.messageId);
        if (senderEmail(m) === inbox.email.toLowerCase()) continue;
        console.log(
          `\n📩 from ${senderEmail(m)}: ${(m.subject || "(no subject)").slice(0, 60)}`,
        );
        try {
          await processMessage(m, inbox);
        } catch (e: any) {
          console.log(`  ! error processing message: ${e.message}`);
        }
      }

      await maybeSendFollowups(inbox);
    } catch (e: any) {
      console.log(`poll error: ${e.message}`);
    }

    await new Promise((r) => setTimeout(r, POLL_MS));
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
