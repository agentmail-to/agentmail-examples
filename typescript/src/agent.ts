/**
 * AgentMail Scheduling Agent — minimal polling loop template.
 *
 * Workflow:
 *   1. Create (or reuse) an AgentMail inbox.
 *   2. Poll for unread messages every POLL_INTERVAL seconds.
 *   3. For each unread message: fetch the full thread, send it to Claude with
 *      the scheduling system prompt, and reply in the same thread.
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
import { buildIcs, icsAttachment } from "./calendarInvite.js";
import { buildSystemPrompt } from "./prompt.js";

// Tool exposed to Claude. When Claude calls this, our code generates an .ics
// file and attaches it to the outgoing reply — no calendar OAuth needed.
const CONFIRM_MEETING_TOOL = {
  name: "confirm_meeting",
  description:
    "Call this when the requester has confirmed a specific date and time. " +
    "It generates a calendar invite (.ics) and attaches it to your reply " +
    "so the requester can add the meeting to their calendar in one click.",
  input_schema: {
    type: "object" as const,
    required: ["title", "start_iso", "duration_minutes"],
    properties: {
      title: {
        type: "string",
        description: "Subject of the meeting, e.g. 'Intro call'",
      },
      start_iso: {
        type: "string",
        description:
          "ISO 8601 start datetime with timezone offset, e.g. " +
          "'2026-05-04T10:00:00-07:00'. Always include the offset.",
      },
      duration_minutes: {
        type: "integer",
        description: "Meeting length in minutes (e.g. 30, 60).",
      },
    },
  },
};

// --- config ------------------------------------------------------------------

const {
  AGENTMAIL_API_KEY,
  ANTHROPIC_API_KEY,
  USER_NAME = "the user",
  USER_EMAIL,
  ANTHROPIC_MODEL = "claude-sonnet-4-6",
  POLL_INTERVAL_SECONDS = "10",
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

// --- helpers -----------------------------------------------------------------

/** Extract the bare email from a message's `from` field.
 *  AgentMail returns it as a string like `'Display Name <user@domain.com>'`. */
function senderEmail(message: any): string {
  const raw = String(message?.from ?? message?.from_ ?? "");
  const match = raw.match(/<([^>]+)>/);
  return (match ? match[1] : raw).trim().toLowerCase();
}

async function getOrCreateInbox(): Promise<any> {
  if (fs.existsSync(STATE_FILE)) {
    try {
      const state = JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
      if (state.inboxId) return await agentmail.inboxes.get(state.inboxId);
    } catch (e: any) {
      console.log(`(stale state, creating new inbox: ${e.message})`);
    }
  }

  const inbox = await agentmail.inboxes.create({
    username: INBOX_USERNAME,
    displayName: `${USER_NAME}'s scheduling agent`,
  });
  fs.writeFileSync(
    STATE_FILE,
    JSON.stringify({ inboxId: inbox.inboxId, email: inbox.email }, null, 2),
  );
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

  // Anthropic requires the first message to be from the user.
  while (msgs.length && msgs[0].role === "assistant") msgs.shift();

  // Anthropic disallows consecutive same-role messages — collapse them.
  const collapsed: typeof msgs = [];
  for (const m of msgs) {
    const last = collapsed[collapsed.length - 1];
    if (last && last.role === m.role) last.content += "\n\n" + m.content;
    else collapsed.push(m);
  }
  return collapsed;
}

async function markRead(inboxId: string, messageId: string) {
  try {
    await agentmail.inboxes.messages.update(inboxId, messageId, {
      removeLabels: ["unread"],
    });
  } catch (e: any) {
    console.log(`  ! couldn't mark read: ${e.message}`);
  }
}

async function processMessage(message: any, inbox: any) {
  console.log(`  → fetching thread ${message.threadId}`);
  const thread = await agentmail.inboxes.threads.get(
    inbox.inboxId,
    message.threadId,
  );

  // If the thread's most recent message is from us, this message has already
  // been superseded by a newer reply. Mark it read and move on.
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
  if (!conversation.length) {
    console.log("  ! empty conversation, skipping");
    await markRead(inbox.inboxId, message.messageId);
    return;
  }

  // Defensive: Anthropic requires the conversation to end with a user turn.
  if (conversation[conversation.length - 1].role !== "user") {
    console.log("  ! conversation does not end with user turn; skipping");
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
    tools: [CONFIRM_MEETING_TOOL],
    messages: conversation,
  });

  // Claude's response can have multiple content blocks: text (the email body)
  // and tool_use (the structured meeting confirmation, if applicable).
  const textParts: string[] = [];
  let inviteArgs:
    | { title: string; start_iso: string; duration_minutes: number }
    | null = null;
  for (const block of response.content) {
    if (block.type === "text") textParts.push(block.text);
    else if (block.type === "tool_use" && block.name === "confirm_meeting") {
      inviteArgs = block.input as any;
    }
  }
  const reply = textParts.join("\n\n").trim() || "Looking forward to it.";

  // If Claude confirmed a slot, build a calendar invite and attach it.
  const requester = senderEmail(message);
  let attachments: any[] | undefined;
  if (inviteArgs) {
    const attendees = [requester];
    if (USER_EMAIL!.toLowerCase() !== requester) {
      attendees.push(USER_EMAIL!.toLowerCase());
    }
    const ics = buildIcs({
      title: inviteArgs.title,
      startIso: inviteArgs.start_iso,
      durationMinutes: Number(inviteArgs.duration_minutes ?? 30),
      organizerEmail: inbox.email,
      attendees,
      description: `Scheduled by ${USER_NAME}'s scheduling agent.`,
    });
    attachments = [icsAttachment(ics)];
  }

  // CC the user on every outgoing reply so they see the conversation in real
  // time. Skip cc if it would land back in the requester's own inbox.
  const cc = USER_EMAIL!.toLowerCase() !== requester ? USER_EMAIL : undefined;

  const extras: string[] = [];
  if (cc) extras.push(`cc=${cc}`);
  if (attachments) extras.push("invite=attached");
  console.log(
    `  → replying (${reply.length} chars${extras.length ? ", " + extras.join(", ") : ""})`,
  );
  await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
    text: reply,
    cc,
    attachments,
  });
  await markRead(inbox.inboxId, message.messageId);
}

// --- main loop ---------------------------------------------------------------

async function main() {
  const inbox = await getOrCreateInbox();
  console.log(`\n📬 Scheduling agent live at: ${inbox.email}`);
  console.log(`   Send an email to that address to test it.`);
  console.log(`   Polling every ${POLL_MS / 1000}s. Ctrl-C to stop.\n`);

  // Defensive: in-process dedup against re-processing if mark-as-read fails.
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
