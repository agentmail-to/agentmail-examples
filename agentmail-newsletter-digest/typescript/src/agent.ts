/**
 * AgentMail Newsletter Digest — daily digest from your inbox.
 *
 * Workflow:
 *   1. Create (or reuse) an AgentMail inbox. Forward your newsletters there.
 *   2. Poll for new mail. For each new email, ask Claude to either summarize
 *      (newsletter) or skip (everything else).
 *   3. Cache summaries to newsletter_cache.json.
 *   4. Once per day at DIGEST_TIME, ask Claude to dedupe + rank + format the
 *      top 5-8, and email the digest to USER_EMAIL.
 *
 * Run:
 *     npm install
 *     cp .env.example .env
 *     npm start
 */

import "dotenv/config";
import * as fs from "node:fs";
import { AgentMailClient } from "agentmail";
import Anthropic from "@anthropic-ai/sdk";
import { isDigestDue, sendDigest } from "./digest.js";
import { appendItem } from "./newsletterCache.js";
import { buildSummarizePrompt } from "./prompt.js";

// --- config ------------------------------------------------------------------

const {
  AGENTMAIL_API_KEY,
  ANTHROPIC_API_KEY,
  USER_NAME = "the user",
  USER_EMAIL,
  DIGEST_TIME = "08:00",
  ANTHROPIC_MODEL = "claude-sonnet-4-6",
  POLL_INTERVAL_SECONDS = "30",
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

// --- per-message tools -------------------------------------------------------

const SAVE_SUMMARY_TOOL = {
  name: "save_summary",
  description:
    "Call this when the email IS a newsletter. Saves a structured summary to the cache for the daily digest.",
  input_schema: {
    type: "object" as const,
    required: ["headline", "key_points", "primary_link", "topic"],
    properties: {
      headline: { type: "string", description: "ONE crisp line — most interesting/actionable item." },
      key_points: { type: "string", description: "1-3 sentence summary of the substance." },
      primary_link: { type: "string", description: "URL representing the headline." },
      topic: { type: "string", description: "Short tag like 'ai-research', 'growth', 'dev-tooling'." },
      importance: { type: "integer", description: "1=interesting, 2=worth surfacing, 3=CTA/deadline/personal", minimum: 1, maximum: 3 },
    },
  },
};

const SKIP_TOOL = {
  name: "skip",
  description: "Call this when the email is NOT a newsletter (transactional, personal, cold outreach).",
  input_schema: {
    type: "object" as const,
    required: ["reason"],
    properties: { reason: { type: "string" } },
  },
};

const PER_MESSAGE_TOOLS = [SAVE_SUMMARY_TOOL, SKIP_TOOL];

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
    displayName: `${USER_NAME}'s newsletter digest`,
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

// --- per-message processing --------------------------------------------------

async function processMessage(message: any, inbox: any) {
  console.log(`  → fetching message body`);
  const full = await agentmail.inboxes.messages.get(inbox.inboxId, message.messageId);
  let body = ((full.extractedText ?? full.text) || "").trim();
  if (!body && full.html) body = full.html;
  if (!body) {
    console.log("  ! empty body, skipping");
    await markRead(inbox.inboxId, message.messageId, ["empty"]);
    return;
  }

  const userPayload = `From: ${full.from}\nSubject: ${full.subject}\n\n---\n${body.slice(0, 8000)}`;

  console.log(`  → asking Claude (model=${ANTHROPIC_MODEL})`);
  const response = await claude.messages.create({
    model: ANTHROPIC_MODEL,
    max_tokens: 1024,
    system: buildSummarizePrompt(),
    tools: PER_MESSAGE_TOOLS,
    tool_choice: { type: "any" },
    messages: [{ role: "user", content: userPayload }],
  });

  for (const block of response.content) {
    if (block.type !== "tool_use") continue;
    const input = block.input as any;
    if (block.name === "save_summary") {
      console.log(`  📝 summary saved (${input.topic ?? "?"}): ${(input.headline ?? "").slice(0, 60)}`);
      appendItem({
        date_iso: new Date().toISOString(),
        headline: input.headline ?? "",
        key_points: input.key_points ?? "",
        primary_link: input.primary_link ?? "",
        topic: input.topic ?? "",
        importance: Number(input.importance ?? 1),
        source_subject: full.subject ?? "",
        source_from: senderEmail(full),
        source_message_id: full.messageId,
      });
      await markRead(inbox.inboxId, full.messageId, ["digested", input.topic ?? "newsletter"]);
      return;
    }
    if (block.name === "skip") {
      console.log(`  ⏭  skipped: ${input.reason ?? ""}`);
      await markRead(inbox.inboxId, full.messageId, ["skipped"]);
      return;
    }
  }
  console.log("  ! Claude did not call any tool");
  await markRead(inbox.inboxId, full.messageId);
}

// --- main loop ---------------------------------------------------------------

async function main() {
  const inbox = await getOrCreateInbox();
  console.log(`\n📬 Newsletter digest agent live at: ${inbox.email}`);
  console.log(`   Forward newsletters there to ingest them.`);
  console.log(`   Daily digest at ${DIGEST_TIME} → ${USER_EMAIL}`);
  console.log(`   Polling every ${POLL_MS / 1000}s. Ctrl-C to stop.\n`);

  const seen = new Set<string>();
  while (true) {
    try {
      const resp = await agentmail.inboxes.messages.list(inbox.inboxId, { labels: ["unread"] });
      const newMsgs = (resp.messages || []).filter((m: any) => !seen.has(m.messageId));
      for (const m of newMsgs) {
        seen.add(m.messageId);
        if (senderEmail(m) === inbox.email.toLowerCase()) continue;
        console.log(`\n📩 from ${senderEmail(m)}: ${(m.subject || "(no subject)").slice(0, 60)}`);
        try { await processMessage(m, inbox); }
        catch (e: any) { console.log(`  ! error processing message: ${e.message}`); }
      }

      const state = loadState();
      if (isDigestDue(DIGEST_TIME, state.lastDigestDate)) {
        const result = await sendDigest({
          claude, agentmail, inbox, model: ANTHROPIC_MODEL, userEmail: USER_EMAIL!,
        });
        if (result.sent) console.log(`   ✅ sent (${result.itemCount} items)\n`);
        else console.log(`   ⏭  skipped: ${result.reason ?? ""}\n`);
        state.lastDigestDate = new Date().toISOString().slice(0, 10);
        saveState(state);
      }
    } catch (e: any) {
      console.log(`poll error: ${e.message}`);
    }
    await new Promise((r) => setTimeout(r, POLL_MS));
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
