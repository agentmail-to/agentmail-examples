/**
 * AgentMail Sales Signal Router — TypeScript port.
 *
 * Per incoming email, Claude calls EXACTLY ONE of four classifier tools:
 *   hot_reply / crm_notification / watchlist_match / noise
 * Then deterministic routing fans the result out to Slack and signals.csv.
 * EOD digest fires once per day at DIGEST_HOUR.
 *
 * Run:
 *   npm install
 *   cp .env.example .env                          # fill API keys + Slack URL
 *   cp watchlist.example.json watchlist.json      # configure watchlist
 *   npm start
 */

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import "dotenv/config";
import { AgentMailClient } from "agentmail";
import Anthropic from "@anthropic-ai/sdk";

import { buildSystemPrompt } from "./prompt.js";
import * as watchlist from "./watchlist.js";
import * as signals from "./signals.js";
import * as slack from "./slack.js";
import * as digest from "./digest.js";

// --- config -------------------------------------------------------------------

const AGENTMAIL_API_KEY = process.env.AGENTMAIL_API_KEY!;
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY!;
const COMPANY_NAME = process.env.COMPANY_NAME || "Sales";
const SALES_LEAD_EMAIL = process.env.SALES_LEAD_EMAIL || "";
const ENTERPRISE_THRESHOLD = parseFloat(process.env.ENTERPRISE_THRESHOLD || "100000");
const MID_MARKET_THRESHOLD = parseFloat(process.env.MID_MARKET_THRESHOLD || "10000");
const DIGEST_HOUR = parseInt(process.env.DIGEST_HOUR || "17", 10);
const MODEL = process.env.ANTHROPIC_MODEL || "claude-sonnet-4-6";
const POLL_INTERVAL = parseInt(process.env.POLL_INTERVAL_SECONDS || "15", 10);
const INBOX_USERNAME = process.env.INBOX_USERNAME || undefined;

if (!process.env.SLACK_WEBHOOK_URL) {
  console.warn("⚠️  SLACK_WEBHOOK_URL not set — alerts will be skipped.");
}

const STATE_FILE = ".agent_state.json";

// --- clients ------------------------------------------------------------------

const agentmail = new AgentMailClient({ apiKey: AGENTMAIL_API_KEY });
const claude = new Anthropic({ apiKey: ANTHROPIC_API_KEY });

// --- Claude tools -------------------------------------------------------------

const TOOLS: Anthropic.Tool[] = [
  {
    name: "hot_reply",
    description: "A human reply on a sales thread showing buying intent, objection, unsubscribe, or out-of-office. Triggers an instant Slack DM to the rep.",
    input_schema: {
      type: "object",
      required: ["sentiment", "summary"],
      properties: {
        sentiment: {
          type: "string",
          enum: ["positive", "objection", "unsubscribe", "ooo"],
          description: "positive=buying intent, objection=worth the rep's time, unsubscribe=opt-out request, ooo=out of office",
        },
        summary: { type: "string", description: "One-line description of why this fired — what they said." },
        deal_owner_hint: { type: "string", description: "Apparent rep on the thread (from sig/cc) if obvious, else empty." },
      },
    },
  },
  {
    name: "crm_notification",
    description: "Automated event from a CRM/billing system (Stripe, HubSpot, Salesforce, Chargebee, Pipedrive, etc.).",
    input_schema: {
      type: "object",
      required: ["event_type", "summary"],
      properties: {
        event_type: {
          type: "string",
          enum: [
            "deal_closed_won", "deal_closed_lost",
            "invoice_paid", "first_invoice",
            "subscription_started", "subscription_upgraded",
            "subscription_canceled", "churn",
            "mrr_change",
          ],
        },
        deal_size_usd: { type: "number", description: "Dollar amount in USD (convert non-USD: EUR×1.08, GBP×1.26, CAD×0.74). 0 if not extractable." },
        customer: { type: "string", description: "Customer name or domain." },
        summary: { type: "string", description: "One-line summary quoting the operative line." },
      },
    },
  },
  {
    name: "watchlist_match",
    description: "Email matches the watchlist (domain/keyword/sender) but isn't already a hot_reply or crm_notification.",
    input_schema: {
      type: "object",
      required: ["matched_term", "why", "summary"],
      properties: {
        matched_term: { type: "string", description: "The specific watchlist entry that matched." },
        why: { type: "string", description: "One-line reason for the match." },
        summary: { type: "string" },
      },
    },
  },
  {
    name: "noise",
    description: "None of the above — newsletter, internal, marketing, delivery status, etc.",
    input_schema: {
      type: "object",
      required: ["reason"],
      properties: { reason: { type: "string", description: "Short tag — newsletter / internal / delivery_status / marketing / other" } },
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
  // Parse "Name <email@x>" or just "email@x"
  const match = String(from).match(/<([^>]+)>/);
  return (match ? match[1] : String(from)).trim().toLowerCase();
}

async function getOrCreateInbox(): Promise<any> {
  const state = loadState();
  if (state.inbox_id) {
    try {
      return await agentmail.inboxes.get(state.inbox_id);
    } catch (e: any) {
      console.log(`(stale state, creating new inbox: ${e.message})`);
    }
  }
  const inbox = await agentmail.inboxes.create({
    username: INBOX_USERNAME,
    displayName: `${COMPANY_NAME} Sales Signals`,
  });
  state.inbox_id = inbox.inboxId;
  state.email = inbox.email;
  saveState(state);
  return inbox;
}

async function markRead(inboxId: string, messageId: string, addLabels: string[] = []): Promise<void> {
  try {
    await agentmail.inboxes.messages.update(inboxId, messageId, {
      removeLabels: ["unread"],
      addLabels,
    });
  } catch (e: any) {
    console.warn(`  ! couldn't mark read: ${e.message}`);
  }
}

function tierFor(amountUsd: number): "enterprise" | "mid_market" | "smb" {
  if (amountUsd >= ENTERPRISE_THRESHOLD) return "enterprise";
  if (amountUsd >= MID_MARKET_THRESHOLD) return "mid_market";
  return "smb";
}

// --- core processing ----------------------------------------------------------

async function processMessage(message: any, inbox: any): Promise<void> {
  const full: any = await agentmail.inboxes.messages.get(inbox.inboxId, message.messageId);

  // Prefer the longer of extracted_text vs raw text
  const extracted = (full.extractedText ?? "").trim();
  const raw = (full.text ?? "").trim();
  const body = raw.length > extracted.length * 1.5 ? raw : (extracted || raw);

  const sender = senderEmail(message);
  const subject = (message.subject ?? "") as string;
  console.log(`  → ${sender}  ·  '${subject.slice(0, 60)}'`);

  // Reload watchlist on every email
  const wl = watchlist.load();

  const userMessage = (
    `From: ${sender}\n` +
    `Subject: ${subject}\n\n` +
    `---WATCHLIST CONTEXT---\n${watchlist.contextBlock(wl)}\n\n` +
    `---EMAIL BODY---\n${body ? body.slice(0, 6000) : "(empty)"}`
  );

  const response = await claude.messages.create({
    model: MODEL,
    max_tokens: 1024,
    system: buildSystemPrompt(inbox.email),
    tools: TOOLS,
    tool_choice: { type: "any" },
    messages: [{ role: "user", content: userMessage }],
  });

  const toolUse = response.content.find((b: any) => b.type === "tool_use") as any;
  if (!toolUse) {
    console.warn("  ! Claude returned no tool call, skipping");
    await markRead(inbox.inboxId, message.messageId, ["signal-error"]);
    return;
  }

  const classification = toolUse.name;
  const args = toolUse.input || {};
  console.log(`  ✓ classification: ${classification}  args: ${JSON.stringify(args).slice(0, 200)}`);

  let slackFired = false;
  let label = `signal-${classification.replace(/_/g, "-")}`;
  let sentimentOrEvent = "";
  let amountUsd = 0;
  let customer = "";
  const summary = args.summary || args.reason || "";

  if (classification === "hot_reply") {
    sentimentOrEvent = args.sentiment || "";
    const ownerSlackId = watchlist.findOwner(wl, sender, body);
    slackFired = await slack.hotReplyAlert({
      sender, summary, sentiment: args.sentiment,
      dealOwnerSlackId: ownerSlackId,
    });
    label = "signal-hot";
  } else if (classification === "crm_notification") {
    amountUsd = Number(args.deal_size_usd ?? 0);
    customer = args.customer ?? "";
    sentimentOrEvent = args.event_type || "";
    const tier = tierFor(amountUsd);
    slackFired = await slack.crmEventAlert({
      sender, eventType: args.event_type, customer,
      dealSizeUsd: amountUsd, tier, summary,
    });
    label = "signal-crm";
  } else if (classification === "watchlist_match") {
    sentimentOrEvent = args.matched_term ?? "";
    slackFired = await slack.watchlistAlert({
      sender, matchedTerm: args.matched_term, why: args.why, summary,
    });
    label = "signal-watchlist";
  } else {
    sentimentOrEvent = args.reason ?? "";
    label = "signal-noise";
  }

  signals.log({
    messageId: message.messageId, sender, classification,
    sentimentOrEvent, amountUsd, customer, summary, slackFired,
  });

  await markRead(inbox.inboxId, message.messageId, [label]);
}

// --- main loop ----------------------------------------------------------------

async function main(): Promise<void> {
  console.log(`--- Sales Signal Router  ·  ${COMPANY_NAME} ---`);
  const inbox = await getOrCreateInbox();
  console.log(`Inbox: ${inbox.email}  (id: ${inbox.inboxId})`);
  console.log(`Polling every ${POLL_INTERVAL}s. Digest at ${DIGEST_HOUR}:00 daily.\n`);

  while (true) {
    try {
      const unread: any = await agentmail.inboxes.messages.list(inbox.inboxId, { labels: ["unread"] });
      const messages: any[] = unread.messages || [];
      if (messages.length) {
        console.log(`[${new Date().toISOString()}] ${messages.length} unread`);
        for (const m of messages) {
          try {
            await processMessage(m, inbox);
          } catch (e: any) {
            console.error(`  ! error on ${m.messageId}: ${e.message}`);
          }
        }
      }

      await digest.maybeSend({
        agentmail, inbox,
        salesLeadEmail: SALES_LEAD_EMAIL,
        hour: DIGEST_HOUR,
      });
    } catch (e: any) {
      console.error(`! poll loop error: ${e.message}`);
    }
    await new Promise(r => setTimeout(r, POLL_INTERVAL * 1000));
  }
}

main().catch(e => { console.error(e); process.exit(1); });
