/**
 * AgentMail Personal Note Taker — TypeScript port.
 *
 * Three classifier tools (extract_note / search_notes / discard).
 * Markdown notes with YAML frontmatter, actions.csv ledger, two-turn search,
 * "done" reply closes out a note's actions, dedupes by thread_id.
 *
 * Run:
 *   npm install
 *   cp .env.example .env
 *   npm start
 */

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import "dotenv/config";
import { AgentMailClient } from "agentmail";
import Anthropic from "@anthropic-ai/sdk";

import { buildClassifyPrompt, buildSearchComposePrompt } from "./prompt.js";
import * as notes from "./notesStore.js";
import * as actions from "./actions.js";
import * as scheduler from "./scheduler.js";

// --- config -------------------------------------------------------------------

const AGENTMAIL_API_KEY = process.env.AGENTMAIL_API_KEY!;
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY!;
const USER_NAME = process.env.USER_NAME || "User";
const USER_EMAIL = process.env.USER_EMAIL!;
const NOTIFY_ASSIGNEES = (process.env.NOTIFY_ASSIGNEES || "false").toLowerCase() === "true";
const DIGEST_HOUR = parseInt(process.env.DIGEST_HOUR || "17", 10);
const DIGEST_WEEKDAY = parseInt(process.env.DIGEST_WEEKDAY || "4", 10);
const REMINDER_HOURS = parseFloat(process.env.REMINDER_HOURS || "24");
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
    name: "extract_note",
    description: "Save the email content as a structured note. Use for emails the user wants to remember.",
    input_schema: {
      type: "object",
      required: ["summary", "tags", "source_summary"],
      properties: {
        summary: { type: "string", description: "One paragraph, ≤60 words." },
        tags: { type: "array", items: { type: "string" }, description: "1-4 short topical labels." },
        source_summary: { type: "string", description: 'e.g. "Fwd from Sarah Chen, 2026-04-29"' },
        decisions: { type: "array", items: { type: "string" } },
        action_items: {
          type: "array",
          items: {
            type: "object",
            required: ["task"],
            properties: {
              owner: { type: "string", description: "Name or email of assignee, empty if unassigned." },
              task: { type: "string" },
              deadline: { type: "string", description: 'ISO "YYYY-MM-DD" or empty.' },
              urgency: { type: "string", enum: ["high", "medium", "low"] },
            },
          },
        },
        open_questions: { type: "array", items: { type: "string" } },
        key_facts: { type: "array", items: { type: "string" } },
      },
    },
  },
  {
    name: "search_notes",
    description: "Search the user's past notes to answer a question they emailed.",
    input_schema: {
      type: "object",
      required: ["query"],
      properties: { query: { type: "string", description: "The user's question." } },
    },
  },
  {
    name: "discard",
    description: "Newsletter, auto-gen, or otherwise not worth saving.",
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
    displayName: `${USER_NAME} Notes`,
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

function isCompletionReply(text: string): boolean {
  if (!text) return false;
  const lines = text.trim().split("\n");
  if (!lines.length) return false;
  const first = lines[0].trim().toLowerCase().replace(/[!.\s]+$/, "");
  return ["done", "complete", "completed", "finished", "✓"].includes(first);
}

// --- formatting ---------------------------------------------------------------

function formatNoteReply(notePath: string, args: any, newActions: actions.ActionRow[]): string {
  const summary = args.summary || "";
  const tags: string[] = args.tags || [];
  const decisions: string[] = args.decisions || [];
  const openQs: string[] = args.open_questions || [];
  const keyFacts: string[] = args.key_facts || [];

  const lines = [
    `Saved note → ${notePath}`,
    "",
    `Tags: ${tags.length ? tags.join(", ") : "(none)"}`,
    "",
    summary,
    "",
  ];
  if (decisions.length) {
    lines.push("Decisions:", ...decisions.map(d => `  • ${d}`), "");
  }
  if (newActions.length) {
    lines.push("Action items:");
    for (const ai of newActions) {
      const owner = ai.owner || "(unassigned)";
      const tail = [ai.deadline, ai.urgency].filter(Boolean).join(" · ");
      const tailStr = tail ? ` — ${tail}` : "";
      lines.push(`  • [${owner}] ${ai.task}${tailStr}`);
    }
    lines.push("");
  }
  if (openQs.length) lines.push("Open questions:", ...openQs.map(q => `  • ${q}`), "");
  if (keyFacts.length) lines.push("Key facts:", ...keyFacts.map(f => `  • ${f}`), "");
  lines.push("Reply 'done' to mark all action items in this note complete.", "", "— Notes assistant");
  return lines.join("\n");
}

// --- search agent (two-turn) --------------------------------------------------

async function runSearch(query: string, inboxEmail: string): Promise<string> {
  const matches = notes.search(query, 8);

  if (!matches.length) {
    return (
      `I couldn't find any notes matching that. You currently have ` +
      `${notes.listAll().length} saved notes. Try narrowing the query or ` +
      `check your tags.\n\n— Notes assistant`
    );
  }

  const contextBlocks = matches.map(m => {
    const excerpt = notes.readNoteExcerpt(m.path, 800);
    return (
      `=== ${m.path} ===\n` +
      `date: ${m.date}  ·  tags: ${m.tags.join(", ")}\n` +
      `source: ${m.source}\n\n${excerpt}`
    );
  }).join("\n\n");

  const response = await claude.messages.create({
    model: MODEL,
    max_tokens: 1024,
    system: buildSearchComposePrompt(inboxEmail),
    messages: [{
      role: "user",
      content:
        `User question:\n${query}\n\n` +
        `Top matching notes:\n\n${contextBlocks}\n\n` +
        `Compose your reply now.`,
    }],
  });

  const text = response.content
    .filter((b: any) => b.type === "text")
    .map((b: any) => b.text)
    .join("\n")
    .trim();
  return text || "(empty response)";
}

// --- core processing ----------------------------------------------------------

async function processMessage(message: any, inbox: any): Promise<void> {
  const full: any = await agentmail.inboxes.messages.get(inbox.inboxId, message.messageId);
  const extracted = (full.extractedText ?? "").trim();
  const raw = (full.text ?? "").trim();
  const body = raw.length > extracted.length * 1.5 ? raw : (extracted || raw);

  const sender = senderEmail(message);
  const subject = (message.subject ?? "") as string;
  const threadId = full.threadId ?? "";
  console.log(`  → ${sender}  ·  '${subject.slice(0, 60)}'  ·  thread ${threadId.slice(0, 24)}`);

  // Skip our own outgoing replies
  if (sender === inbox.email.toLowerCase()) {
    console.log("  · skipping our own outgoing reply");
    await markRead(inbox.inboxId, message.messageId);
    return;
  }

  // "done" reply on a note thread → close out actions
  if (isCompletionReply(body)) {
    const existing = notes.findByThread(threadId);
    if (existing) {
      const n = actions.markDoneForNote(existing);
      console.log(`  ✓ marked ${n} action(s) done for ${existing}`);
      try {
        await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
          text: `Marked ${n} action item(s) as done for ${existing}.\n\n— Notes assistant`,
        });
      } catch (e: any) {
        console.warn(`  ! couldn't ack completion: ${e.message}`);
      }
      await markRead(inbox.inboxId, message.messageId, ["completed"]);
      return;
    }
  }

  // Classify
  const response = await claude.messages.create({
    model: MODEL,
    max_tokens: 2048,
    system: buildClassifyPrompt(inbox.email),
    tools: CLASSIFY_TOOLS,
    tool_choice: { type: "any" },
    messages: [{
      role: "user",
      content:
        `From: ${sender}\nSubject: ${subject}\n\n` +
        `${body ? body.slice(0, 8000) : "(empty body)"}`,
    }],
  });

  const toolUse = response.content.find((b: any) => b.type === "tool_use") as any;
  if (!toolUse) {
    console.warn("  ! Claude returned no tool call");
    await markRead(inbox.inboxId, message.messageId, ["error"]);
    return;
  }

  const name = toolUse.name;
  const args = toolUse.input || {};
  console.log(`  ✓ classification: ${name}`);

  if (name === "extract_note") {
    const existing = threadId ? notes.findByThread(threadId) : null;
    const path = notes.writeNote({
      sourceSummary: args.source_summary || `From ${sender}`,
      threadId,
      tags: args.tags || [],
      summary: args.summary || "",
      decisions: args.decisions || [],
      actionItems: args.action_items || [],
      openQuestions: args.open_questions || [],
      keyFacts: args.key_facts || [],
      existingPath: existing,
    });
    const newActions = actions.appendFromNote(path, args.action_items || []);
    console.log(`  ✓ saved note: ${path}  (+${newActions.length} actions)`);
    try {
      await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, {
        text: formatNoteReply(path, args, newActions),
      });
    } catch (e: any) {
      console.warn(`  ! reply failed: ${e.message}`);
    }
    await markRead(inbox.inboxId, message.messageId, ["note"]);
  }
  else if (name === "search_notes") {
    const query = args.query || body;
    const answer = await runSearch(query, inbox.email);
    try {
      await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, { text: answer });
    } catch (e: any) {
      console.warn(`  ! search reply failed: ${e.message}`);
    }
    await markRead(inbox.inboxId, message.messageId, ["search"]);
  }
  else {
    const reason = args.reason || "noise";
    console.log(`  · discarded (${reason})`);
    await markRead(inbox.inboxId, message.messageId, ["discarded"]);
  }
}

// --- main loop ----------------------------------------------------------------

async function main(): Promise<void> {
  console.log(`--- Personal Note Taker  ·  ${USER_NAME} ---`);
  const inbox = await getOrCreateInbox();
  console.log(`Inbox: ${inbox.email}  (id: ${inbox.inboxId})`);
  console.log(`User:  ${USER_EMAIL}`);
  console.log(`Polling every ${POLL_INTERVAL}s.`);
  console.log(`Reminders: ${REMINDER_HOURS}h before deadline. Notify assignees: ${NOTIFY_ASSIGNEES}.`);
  if (DIGEST_WEEKDAY >= 0) {
    const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    console.log(`Digest: ${days[DIGEST_WEEKDAY]} ${DIGEST_HOUR}:00`);
  }
  console.log();

  while (true) {
    try {
      const unread: any = await agentmail.inboxes.messages.list(inbox.inboxId, { labels: ["unread"] });
      const messages: any[] = unread.messages || [];
      if (messages.length) {
        console.log(`[${new Date().toISOString()}] ${messages.length} unread`);
        for (const m of messages) {
          try { await processMessage(m, inbox); }
          catch (e: any) { console.error(`  ! error on ${m.messageId}: ${e.message}`); }
        }
      }

      await scheduler.fireDueReminders({
        agentmail, inbox, userEmail: USER_EMAIL,
        reminderHours: REMINDER_HOURS, notifyAssignees: NOTIFY_ASSIGNEES,
      });
      await scheduler.maybeSendDigest({
        agentmail, inbox, userEmail: USER_EMAIL,
        hour: DIGEST_HOUR, weekday: DIGEST_WEEKDAY,
      });
    } catch (e: any) {
      console.error(`! poll loop error: ${e.message}`);
    }
    await new Promise(r => setTimeout(r, POLL_INTERVAL * 1000));
  }
}

main().catch(e => { console.error(e); process.exit(1); });
