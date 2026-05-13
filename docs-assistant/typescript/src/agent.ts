/**
 * AgentMail Docs Assistant — answers questions from your docs, escalates the rest.
 *
 * Workflow:
 *   1. Create (or reuse) an AgentMail inbox.
 *   2. Poll for new questions every POLL_INTERVAL seconds.
 *   3. For each question, ask Claude to use the web_search tool (constrained to
 *      your DOCS_URL domain) and either reply with a cited answer OR call the
 *      escalate tool. Escalation forwards the original email to ESCALATION_EMAIL
 *      and sends a short acknowledgment back to the requester.
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

// --- config ------------------------------------------------------------------

const {
  AGENTMAIL_API_KEY,
  ANTHROPIC_API_KEY,
  PRODUCT_NAME = "the product",
  DOCS_URL,
  ESCALATION_EMAIL,
  ANTHROPIC_MODEL = "claude-sonnet-4-6",
  POLL_INTERVAL_SECONDS = "10",
  MAX_SEARCHES_PER_QUESTION = "5",
  INBOX_USERNAME,
} = process.env;

if (!AGENTMAIL_API_KEY) throw new Error("AGENTMAIL_API_KEY required");
if (!ANTHROPIC_API_KEY) throw new Error("ANTHROPIC_API_KEY required");
if (!DOCS_URL) throw new Error("DOCS_URL required");
if (!ESCALATION_EMAIL) throw new Error("ESCALATION_EMAIL required");

const POLL_MS = Number(POLL_INTERVAL_SECONDS) * 1000;
const STATE_FILE = ".agent_state.json";

// Extract bare domain from DOCS_URL (e.g. https://docs.example.com/foo → docs.example.com)
const DOCS_DOMAIN = (() => {
  try {
    return new URL(DOCS_URL).hostname;
  } catch {
    return DOCS_URL;
  }
})();

// --- clients -----------------------------------------------------------------

const agentmail = new AgentMailClient({ apiKey: AGENTMAIL_API_KEY });
const claude = new Anthropic({ apiKey: ANTHROPIC_API_KEY });

// --- Claude tools ------------------------------------------------------------

const WEB_SEARCH_TOOL = {
  type: "web_search_20250305" as const,
  name: "web_search" as const,
  allowed_domains: [DOCS_DOMAIN],
  max_uses: Number(MAX_SEARCHES_PER_QUESTION),
};

const ESCALATE_TOOL = {
  name: "escalate",
  description:
    "Call this when the docs do not contain the answer after a real search. " +
    "The original email will be forwarded to the escalation team with the " +
    "reason you provide. Do NOT call this without first searching the docs.",
  input_schema: {
    type: "object" as const,
    required: ["reason"],
    properties: {
      reason: {
        type: "string",
        description:
          "One-sentence summary of what you searched for and why the docs didn't cover it. Goes in the cover note of the forwarded email.",
      },
    },
  },
};

// --- helpers -----------------------------------------------------------------

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
    displayName: `${PRODUCT_NAME} docs assistant`,
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

function extractTextAndCitations(contentBlocks: any[]) {
  const textParts: string[] = [];
  const citationUrls: string[] = [];
  let escalateArgs: any = null;

  for (const block of contentBlocks) {
    if (block.type === "text") {
      textParts.push(block.text);
      for (const c of block.citations || []) {
        if (c.url) citationUrls.push(c.url);
      }
    } else if (block.type === "tool_use" && block.name === "escalate") {
      escalateArgs = block.input;
    }
  }

  const text = textParts.join("\n\n").trim();
  // Dedup citations preserving order
  const seen = new Set<string>();
  const dedup: string[] = [];
  for (const u of citationUrls) {
    if (!seen.has(u)) {
      seen.add(u);
      dedup.push(u);
    }
  }
  return { text, citations: dedup, escalateArgs };
}

function formatReply(text: string, citations: string[]): string {
  if (!citations.length) return text;
  const label = citations.length === 1 ? "Source" : "Sources";
  const cited = citations.map((u) => `  • ${u}`).join("\n");
  return `${text}\n\n📖 ${label}:\n${cited}`;
}

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
    console.log("  → thread already replied; marking read and skipping");
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
    `  → asking Claude (model=${ANTHROPIC_MODEL}, web_search → ${DOCS_DOMAIN})`,
  );
  const response = await claude.messages.create({
    model: ANTHROPIC_MODEL,
    max_tokens: 2048,
    system,
    tools: [WEB_SEARCH_TOOL, ESCALATE_TOOL],
    messages: conversation,
  });

  const { text, citations, escalateArgs } = extractTextAndCitations(
    response.content,
  );
  const replyBody = text || "Looking into this — will get back to you shortly.";

  if (escalateArgs) {
    const reason = escalateArgs.reason || "Unable to answer from the docs.";
    console.log(`  ⚠️  escalating to ${ESCALATION_EMAIL}: ${reason}`);
    try {
      await agentmail.inboxes.messages.forward(inbox.inboxId, message.messageId, {
        to: [ESCALATION_EMAIL!],
        text: `Couldn't answer from the docs.\n\nAgent's note: ${reason}`,
      });
    } catch (e: any) {
      console.log(`  ! escalation forward failed: ${e.message}`);
    }

    const ack =
      replyBody ||
      "Thanks for reaching out — I'm looping in the team to take a closer look. They'll be in touch.";
    await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
      text: ack,
    });
    await markRead(inbox.inboxId, message.messageId, ["escalated"]);
  } else {
    const reply = formatReply(replyBody, citations);
    console.log(
      `  → replying (${reply.length} chars, ${citations.length} citation(s))`,
    );
    await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
      text: reply,
    });
    await markRead(inbox.inboxId, message.messageId, ["answered"]);
  }
}

// --- main loop ---------------------------------------------------------------

async function main() {
  const inbox = await getOrCreateInbox();
  console.log(`\n📬 Docs assistant live at: ${inbox.email}`);
  console.log(`   Searching: ${DOCS_URL} (domain: ${DOCS_DOMAIN})`);
  console.log(`   Escalating to: ${ESCALATION_EMAIL}`);
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
