/**
 * AgentMail Inbox Zero Agent — drafts replies while you sleep.
 *
 * Workflow:
 *   1. Create (or reuse) an AgentMail inbox.
 *   2. Poll for new mail every POLL_INTERVAL seconds.
 *   3. For each new email: ask Claude to classify and either draft a reply,
 *      flag for human, or mark handled.
 *   4. Once per day at WAKE_TIME, email USER_EMAIL a digest of overnight activity.
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
import { buildDigestText, isDigestDue } from "./digest.js";
import { buildSystemPrompt } from "./prompt.js";

// --- config ------------------------------------------------------------------

const {
  AGENTMAIL_API_KEY,
  ANTHROPIC_API_KEY,
  USER_NAME = "the user",
  USER_EMAIL,
  ANTHROPIC_MODEL = "claude-sonnet-4-6",
  POLL_INTERVAL_SECONDS = "20",
  WAKE_TIME = "08:00",
  INBOX_USERNAME,
} = process.env;

if (!AGENTMAIL_API_KEY) throw new Error("AGENTMAIL_API_KEY required");
if (!ANTHROPIC_API_KEY) throw new Error("ANTHROPIC_API_KEY required");
if (!USER_EMAIL) throw new Error("USER_EMAIL required");

const POLL_MS = Number(POLL_INTERVAL_SECONDS) * 1000;
const STATE_FILE = ".agent_state.json";

// --- clients -----------------------------------------------------------------

const agentmail = new AgentMailClient({ apiKey: AGENTMAIL_API_KEY });
const claude = new Anthropic({ apiKey: ANTHROPIC_API_KEY });

// --- Claude tools ------------------------------------------------------------

const TOOLS = [
  {
    name: "draft_reply",
    description:
      "Save a draft reply to the source email. The draft lands in the " +
      "drafts folder for the user to review and send manually. Use for " +
      "emails that need a substantive response.",
    input_schema: {
      type: "object" as const,
      required: ["text"],
      properties: {
        text: {
          type: "string",
          description:
            "The body of the reply, in the user's voice. Plain text only.",
        },
      },
    },
  },
  {
    name: "flag_for_human",
    description:
      "Mark the email as needing the user's attention without drafting " +
      "a reply. Use when the email needs a decision, commitment, or " +
      "sensitive judgment that should not be auto-drafted.",
    input_schema: {
      type: "object" as const,
      required: ["reason"],
      properties: {
        reason: {
          type: "string",
          description:
            "One sentence on why this needs human attention (shown in the morning digest).",
        },
      },
    },
  },
  {
    name: "mark_handled",
    description:
      "Mark the email as handled — no draft, no flag. Use for spam, " +
      "promotional, FYI, or auto-notifications the user does not need to act on.",
    input_schema: {
      type: "object" as const,
      required: ["category"],
      properties: {
        category: {
          type: "string",
          enum: ["fyi", "spam", "promotional", "auto_notification"],
          description: "Why this email doesn't need action.",
        },
        note: {
          type: "string",
          description: "Optional one-line context.",
        },
      },
    },
  },
];

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
    displayName: `${USER_NAME}'s inbox-zero agent`,
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

async function handleDraftReply(args: any, message: any, inbox: any) {
  const text = String(args.text || "").trim();
  if (!text) {
    console.log("  ! draft_reply called with empty text, skipping");
    return;
  }
  const requester = senderEmail(message);
  let subject = message.subject || "(no subject)";
  if (!subject.toLowerCase().startsWith("re:")) subject = `Re: ${subject}`;

  const draft = await agentmail.inboxes.drafts.create(inbox.inboxId, {
    inReplyTo: message.messageId,
    to: requester ? [requester] : undefined,
    subject,
    text,
  });
  console.log(`  📝 draft saved: ${draft.draftId} → ${requester}`);
  await markRead(inbox.inboxId, message.messageId, ["drafted"]);
}

async function handleFlagForHuman(args: any, message: any, inbox: any) {
  const reason = String(args.reason || "").trim();
  console.log(`  ⚠️  flagged for human: ${reason}`);
  await markRead(inbox.inboxId, message.messageId, ["needs_human"]);
}

async function handleMarkHandled(args: any, message: any, inbox: any) {
  const category = String(args.category || "fyi");
  const note = String(args.note || "").trim();
  console.log(`  ✓ handled as ${category}${note ? ` — ${note}` : ""}`);
  await markRead(inbox.inboxId, message.messageId, [category]);
}

const TOOL_HANDLERS: Record<
  string,
  (args: any, message: any, inbox: any) => Promise<void>
> = {
  draft_reply: handleDraftReply,
  flag_for_human: handleFlagForHuman,
  mark_handled: handleMarkHandled,
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
    console.log("  → thread already handled; marking read and skipping");
    await markRead(inbox.inboxId, message.messageId);
    return;
  }

  const conversation = threadToMessages(thread, inbox.email);
  if (
    !conversation.length ||
    conversation[conversation.length - 1].role !== "user"
  ) {
    console.log("  ! no user content to act on, marking read");
    await markRead(inbox.inboxId, message.messageId);
    return;
  }

  const system = buildSystemPrompt({ inboxEmail: inbox.email });
  console.log(
    `  → asking Claude (model=${ANTHROPIC_MODEL}, ${conversation.length} turn(s))`,
  );
  const response = await claude.messages.create({
    model: ANTHROPIC_MODEL,
    max_tokens: 1024,
    system,
    tools: TOOLS,
    tool_choice: { type: "any" },
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
    console.log("  ! Claude did not call any tool, marking read defensively");
    await markRead(inbox.inboxId, message.messageId);
  }
}

// --- digest ------------------------------------------------------------------

async function maybeSendDigest(inbox: any) {
  const state = loadState();
  if (!isDigestDue(WAKE_TIME, state.lastDigestDate)) return;

  console.log(`\n📨 Sending morning digest to ${USER_EMAIL}…`);

  const draftsResp = await agentmail.inboxes.drafts.list(inbox.inboxId);
  const drafts = draftsResp.drafts || [];

  const flaggedResp = await agentmail.inboxes.messages.list(inbox.inboxId, {
    labels: ["needs_human"],
  });
  const flagged = flaggedResp.messages || [];

  const body = buildDigestText({
    userName: USER_NAME,
    inboxEmail: inbox.email,
    drafts,
    flagged,
  });
  const todayStr = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  await agentmail.inboxes.messages.send(inbox.inboxId, {
    to: [USER_EMAIL!],
    subject: `Inbox digest — ${todayStr}`,
    text: body,
  });

  state.lastDigestDate = new Date().toISOString().slice(0, 10);
  saveState(state);
  console.log(`   sent (${drafts.length} draft(s), ${flagged.length} flagged)\n`);
}

// --- main loop ---------------------------------------------------------------

async function main() {
  const inbox = await getOrCreateInbox();
  console.log(`\n📬 Inbox-zero agent live at: ${inbox.email}`);
  console.log(`   Forward mail there to test it.`);
  console.log(
    `   Polling every ${POLL_MS / 1000}s. Morning digest at ${WAKE_TIME} → ${USER_EMAIL}.`,
  );
  console.log(`   Ctrl-C to stop.\n`);

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

      await maybeSendDigest(inbox);
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
