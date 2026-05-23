/**
 * Email Triage Agent — built with OpenAI Agents SDK (JS) + AgentMail.
 *
 * Gives an autonomous agent its own email inbox. The agent reads incoming
 * messages, classifies them, drafts replies, and either sends them directly
 * or escalates to a human depending on confidence.
 *
 * Run:
 *   npm install
 *   cp .env.example .env   # fill in your keys
 *   npx tsx src/agent.ts
 */

import { AgentMail } from "agentmail";
import { Agent, run, tool } from "@openai/agents";
import { z } from "zod";
import "dotenv/config";

// --- config -------------------------------------------------------------------

const AGENTMAIL_API_KEY = process.env.AGENTMAIL_API_KEY!;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY!;
const ESCALATION_EMAIL = process.env.ESCALATION_EMAIL!;
const PRODUCT_NAME = process.env.PRODUCT_NAME ?? "Acme Corp";
const AGENT_NAME = process.env.AGENT_NAME ?? "Alex";
const MODEL = process.env.OPENAI_MODEL ?? "gpt-4o";
const POLL_INTERVAL = parseInt(process.env.POLL_INTERVAL_SECONDS ?? "10", 10);
const INBOX_USERNAME = process.env.INBOX_USERNAME ?? undefined;

const CATEGORIES = [
  "billing",
  "bug_report",
  "feature_request",
  "question",
  "spam",
  "urgent",
] as const;

// --- clients ------------------------------------------------------------------

const mail = new AgentMail({ apiKey: AGENTMAIL_API_KEY });

// --- helpers ------------------------------------------------------------------

function senderEmail(message: any): string {
  const from = message.from_ ?? message.from ?? "";
  const match = String(from).match(/<(.+?)>/);
  return (match ? match[1] : String(from)).toLowerCase();
}

function buildThreadContext(thread: any, ourEmail: string): string {
  const lines: string[] = [];
  for (const m of thread.messages ?? []) {
    const who = senderEmail(m);
    const role =
      who === ourEmail.toLowerCase() ? "Agent" : `Customer (${who})`;
    const body = (m.extractedText ?? m.text ?? "").trim();
    if (body) lines.push(`[${role}]:\n${body}`);
  }
  return lines.length ? lines.join("\n\n---\n\n") : "(empty thread)";
}

// --- state -------------------------------------------------------------------

import { readFileSync, writeFileSync, existsSync } from "fs";
const STATE_FILE = ".agent_state.json";

function loadState(): Record<string, any> {
  if (existsSync(STATE_FILE)) {
    try {
      return JSON.parse(readFileSync(STATE_FILE, "utf-8"));
    } catch {
      return {};
    }
  }
  return {};
}

function saveState(state: Record<string, any>): void {
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

// --- tools -------------------------------------------------------------------

const replyToEmail = tool({
  name: "reply_to_email",
  description:
    "Send a reply to an email and label it with a category.",
  parameters: z.object({
    inboxId: z.string().describe("The inbox ID"),
    messageId: z.string().describe("The message ID to reply to"),
    text: z.string().describe("The reply body"),
    category: z.enum(CATEGORIES).describe("Email category"),
  }),
  execute: async ({ inboxId, messageId, text, category }) => {
    await mail.inboxes.messages.reply(inboxId, messageId, { text });
    try {
      await mail.inboxes.messages.update(inboxId, messageId, {
        removeLabels: ["unread"],
        addLabels: [category, "auto-replied"],
      });
    } catch {}
    return `Reply sent and labeled as '${category}'.`;
  },
});

const escalateToHuman = tool({
  name: "escalate_to_human",
  description:
    "Forward an email to the human team when the agent can't confidently respond.",
  parameters: z.object({
    inboxId: z.string().describe("The inbox ID"),
    messageId: z.string().describe("The message ID to escalate"),
    reason: z.string().describe("Why this needs human attention"),
    category: z.enum(CATEGORIES).describe("Email category"),
  }),
  execute: async ({ inboxId, messageId, reason, category }) => {
    await mail.inboxes.messages.forward(inboxId, messageId, {
      to: [ESCALATION_EMAIL],
      text: `[${category.toUpperCase()} — ESCALATION] ${reason}`,
    });
    await mail.inboxes.messages.reply(inboxId, messageId, {
      text: "Thanks for reaching out. I've flagged this for our team and someone will follow up with you shortly.",
    });
    try {
      await mail.inboxes.messages.update(inboxId, messageId, {
        removeLabels: ["unread"],
        addLabels: [category, "escalated"],
      });
    } catch {}
    return `Escalated. Category: ${category}. Reason: ${reason}`;
  },
});

const skipMessage = tool({
  name: "skip_message",
  description: "Skip a message (spam, auto-reply, or not actionable).",
  parameters: z.object({
    inboxId: z.string().describe("The inbox ID"),
    messageId: z.string().describe("The message to skip"),
    reason: z.string().describe("Why the message is being skipped"),
  }),
  execute: async ({ inboxId, messageId, reason }) => {
    try {
      await mail.inboxes.messages.update(inboxId, messageId, {
        removeLabels: ["unread"],
        addLabels: ["skipped"],
      });
    } catch {}
    return `Message skipped: ${reason}`;
  },
});

// --- agent -------------------------------------------------------------------

const triageAgent = new Agent({
  name: "EmailTriageAgent",
  instructions: `You are ${AGENT_NAME}, an email triage agent for ${PRODUCT_NAME}.

Your job is to process incoming emails. For each email:

1. Read the full conversation thread for context.
2. Classify the email into one of: ${CATEGORIES.join(", ")}.
3. Decide on an action:
   - reply_to_email: You're confident you can answer.
   - escalate_to_human: Complex, sensitive, or unsure.
   - skip_message: Spam, auto-reply, or no-reply address.

Guidelines:
- Be helpful, professional, and concise.
- Sign replies as "${AGENT_NAME}, ${PRODUCT_NAME} Support".
- Never promise things you can't verify — escalate those.
- For billing and urgent issues, prefer escalation.`,
  model: MODEL as any,
  tools: [replyToEmail, escalateToHuman, skipMessage],
});

// --- inbox management --------------------------------------------------------

async function getOrCreateInbox() {
  const state = loadState();
  if (state.inboxId) {
    try {
      return await mail.inboxes.get(state.inboxId);
    } catch (e) {
      console.log(`(stale inbox, creating new: ${e})`);
    }
  }

  const inbox = await mail.inboxes.create({
    username: INBOX_USERNAME,
    displayName: `${PRODUCT_NAME} Triage`,
  });
  state.inboxId = inbox.inboxId;
  state.email = inbox.email;
  saveState(state);
  return inbox;
}

// --- main loop ---------------------------------------------------------------

async function processMessage(message: any, inbox: any) {
  console.log(`  → fetching thread ${message.threadId}`);
  const thread = await mail.inboxes.threads.get(inbox.inboxId, message.threadId);
  const context = buildThreadContext(thread, inbox.email);

  const prompt = [
    `New email in inbox ${inbox.inboxId}.`,
    `Message ID: ${message.messageId}`,
    `From: ${senderEmail(message)}`,
    `Subject: ${message.subject ?? "(no subject)"}`,
    `\n--- Thread ---\n${context}`,
    `\nTriage this email. Use exactly one tool.`,
  ].join("\n");

  const result = await run(triageAgent, prompt);
  console.log(`  ✓ agent output: ${String(result.finalOutput).slice(0, 120)}...`);
}

async function main() {
  const inbox = await getOrCreateInbox();
  console.log(`\n📬 Email triage agent live at: ${inbox.email}`);
  console.log(`   Escalating to: ${ESCALATION_EMAIL}`);
  console.log(`   Model: ${MODEL}`);
  console.log(`   Polling every ${POLL_INTERVAL}s. Ctrl-C to stop.\n`);

  const seen = new Set<string>();

  while (true) {
    try {
      const resp = await mail.inboxes.messages.list(inbox.inboxId, {
        labels: ["unread"],
      });
      const newMsgs = (resp.messages ?? []).filter(
        (m: any) => !seen.has(m.messageId)
      );
      for (const m of newMsgs) {
        seen.add(m.messageId);
        if (senderEmail(m) === inbox.email.toLowerCase()) continue;
        console.log(
          `\n📩 from ${senderEmail(m)}: ${(m.subject ?? "(no subject)").slice(0, 60)}`
        );
        try {
          await processMessage(m, inbox);
        } catch (e) {
          console.error(`  ! error processing: ${e}`);
        }
      }
    } catch (e) {
      console.error(`poll error: ${e}`);
    }
    await new Promise((r) => setTimeout(r, POLL_INTERVAL * 1000));
  }
}

main().catch(console.error);
