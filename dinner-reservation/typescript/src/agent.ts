/**
 * AgentMail Dinner Reservation Agent — emails restaurants on your behalf,
 * handles their replies, confirms your booking with a calendar invite.
 */

import "dotenv/config";
import * as fs from "node:fs";
import { randomUUID } from "node:crypto";
import { AgentMailClient } from "agentmail";
import Anthropic from "@anthropic-ai/sdk";
import { buildIcs, icsAttachment } from "./calendarInvite.js";
import * as reservations from "./reservations.js";
import { buildSystemPrompt } from "./prompt.js";

// --- config ------------------------------------------------------------------

const {
  AGENTMAIL_API_KEY,
  ANTHROPIC_API_KEY,
  USER_NAME = "the user",
  USER_EMAIL,
  ANTHROPIC_MODEL = "claude-sonnet-4-6",
  POLL_INTERVAL_SECONDS = "15",
  INBOX_USERNAME,
} = process.env;

if (!AGENTMAIL_API_KEY) throw new Error("AGENTMAIL_API_KEY required");
if (!ANTHROPIC_API_KEY) throw new Error("ANTHROPIC_API_KEY required");
if (!USER_EMAIL) throw new Error("USER_EMAIL required");

const USER_EMAIL_LC = USER_EMAIL.toLowerCase();
const POLL_MS = Number(POLL_INTERVAL_SECONDS) * 1000;
const STATE_FILE = ".agent_state.json";

// --- clients -----------------------------------------------------------------

const agentmail = new AgentMailClient({ apiKey: AGENTMAIL_API_KEY });
const claude = new Anthropic({ apiKey: ANTHROPIC_API_KEY });

// --- tools -------------------------------------------------------------------

const TOOLS = [
  {
    name: "email_restaurant",
    description: "Send the booking request to the restaurant. Use ONLY when you have all required details.",
    input_schema: {
      type: "object" as const,
      required: ["restaurant_email", "restaurant_name", "date", "time", "party_size", "message"],
      properties: {
        restaurant_email: { type: "string" },
        restaurant_name: { type: "string" },
        date: { type: "string" },
        time: { type: "string" },
        party_size: { type: "integer" },
        dietary: { type: "string" },
        message: { type: "string", description: "Email body, under 80 words, professional, asks for reply confirmation." },
      },
    },
  },
  {
    name: "ask_user",
    description: "Reply to the user's thread with ONE specific clarifying question.",
    input_schema: {
      type: "object" as const,
      required: ["question"],
      properties: { question: { type: "string" } },
    },
  },
  {
    name: "confirm_to_user",
    description: "Restaurant confirmed. Reply to the user's thread with structured confirmation, and attach a .ics calendar invite.",
    input_schema: {
      type: "object" as const,
      required: ["restaurant_name", "date", "time", "party_size", "start_iso", "summary"],
      properties: {
        restaurant_name: { type: "string" },
        date: { type: "string" },
        time: { type: "string" },
        start_iso: { type: "string", description: "ISO 8601 start datetime with timezone offset, e.g. '2026-05-01T19:00:00-07:00'." },
        duration_minutes: { type: "integer", description: "Default 90 for dinner." },
        party_size: { type: "integer" },
        restaurant_contact: { type: "string" },
        summary: { type: "string" },
      },
    },
  },
  {
    name: "forward_alternative_to_user",
    description: "Restaurant offered a different date/time.",
    input_schema: {
      type: "object" as const,
      required: ["restaurant_name", "alternative_offered", "summary"],
      properties: {
        restaurant_name: { type: "string" },
        alternative_offered: { type: "string" },
        summary: { type: "string" },
      },
    },
  },
  {
    name: "tell_user_decline",
    description: "Restaurant declined or fully booked.",
    input_schema: {
      type: "object" as const,
      required: ["restaurant_name", "reason"],
      properties: {
        restaurant_name: { type: "string" },
        reason: { type: "string" },
        suggestion: { type: "string" },
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

async function getOrCreateInbox(): Promise<any> {
  const state = loadState();
  if (state.inboxId) {
    try { return await agentmail.inboxes.get(state.inboxId); }
    catch (e: any) { console.log(`(stale state, creating new inbox: ${e.message})`); }
  }
  const inbox = await agentmail.inboxes.create({
    username: INBOX_USERNAME,
    displayName: `${USER_NAME}'s reservation agent`,
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

function classifySender(message: any): "user" | "restaurant" | "unknown" {
  if (reservations.findByRestaurantThread(message.threadId)) return "restaurant";
  if (senderEmail(message) === USER_EMAIL_LC) return "user";
  return "unknown";
}

// --- thread reply helper -----------------------------------------------------

async function replyInUserThread(
  reservation: reservations.Reservation,
  body: string,
  inbox: any,
  attachments?: any[],
) {
  const userThreadId = reservation.user_thread_id;
  if (!userThreadId) {
    await agentmail.inboxes.messages.send(inbox.inboxId, {
      to: [USER_EMAIL!],
      subject: `Reservation update — ${reservation.restaurant_name ?? ""}`,
      text: body,
      attachments,
    });
    return;
  }
  const thread = await agentmail.inboxes.threads.get(inbox.inboxId, userThreadId);
  const userMsgs = (thread.messages || []).filter(
    (m: any) => senderEmail(m) === USER_EMAIL_LC,
  );
  const target = userMsgs[userMsgs.length - 1] || (thread.messages?.[thread.messages.length - 1]);
  if (target) {
    await agentmail.inboxes.messages.reply(inbox.inboxId, target.messageId, {
      text: body,
      attachments,
    });
  } else {
    await agentmail.inboxes.messages.send(inbox.inboxId, {
      to: [USER_EMAIL!],
      subject: "Reservation update",
      text: body,
      attachments,
    });
  }
}

// --- tool handlers -----------------------------------------------------------

async function handleEmailRestaurant(args: any, message: any, inbox: any) {
  const rid = randomUUID().slice(0, 8);
  console.log(`  📧 emailing restaurant ${args.restaurant_name} (${args.restaurant_email})`);
  const subject = `Reservation Request — ${args.date} — Party of ${args.party_size}`;
  const sent = await agentmail.inboxes.messages.send(inbox.inboxId, {
    to: [args.restaurant_email],
    subject,
    text: args.message,
  });

  const restaurantThreadId = sent.threadId ?? sent.messageId;
  reservations.upsert(rid, {
    status: "awaiting_restaurant",
    restaurant_email: args.restaurant_email,
    restaurant_name: args.restaurant_name,
    restaurant_thread_id: restaurantThreadId,
    user_thread_id: message.threadId,
    details: {
      date: args.date,
      time: args.time,
      party_size: args.party_size,
      dietary: args.dietary || "",
    },
  });

  const ack =
    `Got it — emailing ${args.restaurant_name} now to request a table for ` +
    `${args.party_size} on ${args.date} at ${args.time}. ` +
    `I'll forward their reply as soon as it lands.`;
  await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, { text: ack });
}

async function handleAskUser(args: any, message: any, inbox: any) {
  console.log(`  ❓ asking user: ${(args.question ?? "").slice(0, 80)}`);
  await agentmail.inboxes.messages.reply(inbox.inboxId, message.messageId, { text: args.question });
}

async function handleConfirmToUser(args: any, message: any, inbox: any) {
  const rec = reservations.findByRestaurantThread(message.threadId) || {
    id: undefined as any, status: "fallback", created_at: new Date().toISOString(),
    restaurant_name: args.restaurant_name,
  } as reservations.Reservation;

  console.log(`  ✅ confirming to user: ${args.restaurant_name} on ${args.date} at ${args.time}`);

  const contact = (args.restaurant_contact ?? "").trim();
  const contactLine = contact ? `\nConfirmed by: ${contact}` : "";
  const body =
    `CONFIRMED ✓\n\n` +
    `Restaurant: ${args.restaurant_name}\n` +
    `Date: ${args.date} at ${args.time}\n` +
    `Party: ${args.party_size} people` +
    `${contactLine}\n\n` +
    `${args.summary}\n\n` +
    `📅 Calendar invite attached — open it to add to your calendar.`;

  let attachments: any[] | undefined;
  try {
    const attendees = [USER_EMAIL!];
    if (rec.restaurant_email) attendees.push(rec.restaurant_email);
    const ics = buildIcs({
      title: `Dinner at ${args.restaurant_name} (party of ${args.party_size})`,
      startIso: args.start_iso,
      durationMinutes: Number(args.duration_minutes ?? 90),
      organizerEmail: inbox.email,
      attendees,
      description: args.summary || "",
    });
    const filename = `dinner-${String(args.restaurant_name).toLowerCase().replace(/\s+/g, "-")}.ics`;
    attachments = [icsAttachment(ics, filename)];
    console.log(`  📅 calendar invite attached (${args.start_iso}, ${args.duration_minutes ?? 90} min)`);
  } catch (e: any) {
    console.log(`  ! couldn't build calendar invite: ${e.message}`);
  }

  await replyInUserThread(rec, body, inbox, attachments);
  if (rec.id) reservations.upsert(rec.id, { status: "confirmed" });
}

async function handleForwardAlternative(args: any, message: any, inbox: any) {
  const rec = reservations.findByRestaurantThread(message.threadId);
  console.log(`  ↪  alternative from ${args.restaurant_name}: ${args.alternative_offered}`);
  const body =
    `ALTERNATIVE OFFERED ↪\n\n${args.restaurant_name} can't do the original time. ` +
    `They suggested: ${args.alternative_offered}\n\n${args.summary}\n\n` +
    `Reply with 'yes' to take it, or tell me what to do instead.`;
  if (rec) {
    await replyInUserThread(rec, body, inbox);
    if (rec.id) reservations.upsert(rec.id, {
      status: "alternative_offered",
      alternative: args.alternative_offered,
    });
  }
}

async function handleTellUserDecline(args: any, message: any, inbox: any) {
  const rec = reservations.findByRestaurantThread(message.threadId);
  console.log(`  ✗ ${args.restaurant_name} declined: ${args.reason}`);
  const suggestion = (args.suggestion ?? "").trim();
  const body =
    `DECLINED ✗\n\n${args.restaurant_name}: ${args.reason}\n\n` +
    `${suggestion || "Want me to try another time or another restaurant? Just reply with the details."}`;
  if (rec) {
    await replyInUserThread(rec, body, inbox);
    if (rec.id) reservations.upsert(rec.id, { status: "declined" });
  }
}

const TOOL_HANDLERS: Record<string, (args: any, message: any, inbox: any) => Promise<void>> = {
  email_restaurant: handleEmailRestaurant,
  ask_user: handleAskUser,
  confirm_to_user: handleConfirmToUser,
  forward_alternative_to_user: handleForwardAlternative,
  tell_user_decline: handleTellUserDecline,
};

// --- core processing ---------------------------------------------------------

async function processMessage(message: any, inbox: any) {
  const senderKind = classifySender(message);
  console.log(`  → sender_kind=${senderKind}`);

  if (senderKind === "unknown") {
    await markRead(inbox.inboxId, message.messageId, ["unknown_sender"]);
    return;
  }

  const thread = await agentmail.inboxes.threads.get(inbox.inboxId, message.threadId);
  const fullMsgs = thread.messages || [];
  if (!fullMsgs.length) {
    await markRead(inbox.inboxId, message.messageId);
    return;
  }
  const latest = fullMsgs[fullMsgs.length - 1];
  const body = ((latest.extractedText ?? latest.text) || "").trim();

  let contextHeader: string;
  if (senderKind === "user") {
    contextHeader = `[INBOUND USER REQUEST]\nFrom: ${latest.from}\nSubject: ${latest.subject}\n\n`;
  } else {
    const rec = reservations.findByRestaurantThread(message.threadId);
    contextHeader =
      `[RESTAURANT REPLY]\n` +
      `Restaurant: ${rec?.restaurant_name ?? "?"}\n` +
      `Original request: ${JSON.stringify(rec?.details ?? {})}\n` +
      `From: ${latest.from}\nSubject: ${latest.subject}\n\n`;
  }

  const userPayload = contextHeader + (body.slice(0, 4000) || "(empty body)");

  console.log(`  → asking Claude (model=${ANTHROPIC_MODEL})`);
  const response = await claude.messages.create({
    model: ANTHROPIC_MODEL,
    max_tokens: 2048,
    system: buildSystemPrompt({ inboxEmail: inbox.email }),
    tools: TOOLS,
    tool_choice: { type: "any" },
    messages: [{ role: "user", content: userPayload }],
  });

  let handled = false;
  for (const block of response.content) {
    if (block.type === "tool_use" && TOOL_HANDLERS[block.name]) {
      try {
        await TOOL_HANDLERS[block.name](block.input, message, inbox);
        handled = true;
        await markRead(inbox.inboxId, message.messageId, [senderKind, block.name]);
      } catch (e: any) {
        console.log(`  ! tool handler ${block.name} failed: ${e.message}`);
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
  console.log(`\n📬 Reservation agent live at: ${inbox.email}`);
  console.log(`   Email reservation requests there from ${USER_EMAIL}.`);
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
    } catch (e: any) {
      console.log(`poll error: ${e.message}`);
    }
    await new Promise((r) => setTimeout(r, POLL_MS));
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
