/**
 * AgentMail Verified Outreach - TypeScript.
 *
 * Verify every prospect with MailVeri before the agent sends the first touch.
 * VALID -> send, INVALID / DISPOSABLE / FULL_INBOX -> skip,
 * ROLE_ACCOUNT / CATCH_ALL / UNKNOWN -> hold for review (configurable).
 */

import "dotenv/config";
import * as fs from "node:fs";
import { AgentMailClient } from "agentmail";
import * as mailveri from "./mailveri.js";
import * as prospects from "./prospects.js";

// --- config ------------------------------------------------------------------

const flag = (v?: string) => ["1", "true", "yes"].includes((v ?? "").trim().toLowerCase());

const {
  AGENTMAIL_API_KEY,
  MAILVERI_API_KEY,
  SENDER_NAME = "Sender",
  SENDER_COMPANY = "Company",
  VERIFY_INTERVAL_SECONDS = "1.1",
  INBOX_USERNAME,
} = process.env;

if (!AGENTMAIL_API_KEY) throw new Error("AGENTMAIL_API_KEY required");
if (!MAILVERI_API_KEY) throw new Error("MAILVERI_API_KEY required");

const SEND_ROLE_ACCOUNTS = flag(process.env.SEND_ROLE_ACCOUNTS);
const SEND_CATCH_ALL = flag(process.env.SEND_CATCH_ALL);
const DRY_RUN = flag(process.env.DRY_RUN);
const VERIFY_INTERVAL_MS = Number(VERIFY_INTERVAL_SECONDS) * 1000;
const STATE_FILE = ".agent_state.json";

const agentmail = new AgentMailClient({ apiKey: AGENTMAIL_API_KEY });
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// --- inbox -------------------------------------------------------------------

async function getOrCreateInbox(): Promise<any> {
  const state = fs.existsSync(STATE_FILE) ? JSON.parse(fs.readFileSync(STATE_FILE, "utf8")) : {};
  if (state.inboxId) {
    try { return await agentmail.inboxes.get(state.inboxId); }
    catch (e: any) { console.log(`(stale state, creating new inbox: ${e.message})`); }
  }
  const inbox = await agentmail.inboxes.create({
    username: INBOX_USERNAME,
    displayName: `${SENDER_NAME} - ${SENDER_COMPANY}`,
  });
  fs.writeFileSync(STATE_FILE, JSON.stringify({ inboxId: inbox.inboxId, email: inbox.email }, null, 2));
  return inbox;
}

// --- message -----------------------------------------------------------------
// A plain template keeps this example focused on the verification gate. To use
// an LLM writer instead, swap in writeEmailBody() from ../../gtm-agent.

function compose(p: prospects.Prospect): { subject: string; body: string } {
  const first = p.name.split(/\s+/).filter(Boolean)[0] || "there";
  const subject = p.company ? `Quick question about ${p.company}` : "Quick question";
  const body =
    `Hi ${first},\n\n` +
    `Saw that ${p.hook.replace(/\.$/, "")}. Would a 15-minute call next week be useful?\n\n` +
    `${SENDER_NAME}\n${SENDER_COMPANY}`;
  return { subject, body };
}

// --- verification gate -------------------------------------------------------

async function verifyWithRetry(email: string): Promise<mailveri.Verification> {
  try {
    return await mailveri.verify(email, MAILVERI_API_KEY!);
  } catch (e: any) {
    if (e instanceof mailveri.MailVeriError && e.fatal) throw e;
    console.log(`    ! ${e.message}, retrying once`);
    await sleep(2000);
    return mailveri.verify(email, MAILVERI_API_KEY!);
  }
}

async function processProspect(p: prospects.Prospect, inbox: any): Promise<void> {
  const email = p.email;
  console.log(`\n🔎 ${email}`);

  let result: mailveri.Verification;
  try {
    result = await verifyWithRetry(email);
  } catch (e: any) {
    if (e instanceof mailveri.MailVeriError && e.fatal) throw e;
    // Leave the row queued so the next run tries again. Never send unverified.
    console.log(`    ! verification failed, left queued: ${e.message}`);
    prospects.log({ email, mailveri_status: "ERROR", decision: "retry_later", note: e.message });
    return;
  }

  const decision = mailveri.decide(result.status, SEND_ROLE_ACCOUNTS, SEND_CATCH_ALL);
  console.log(`    MailVeri: ${result.status} -> ${decision} (credits left: ${result.balance})`);
  prospects.updateProspect(email, { verify_status: result.status, verified_at: prospects.nowIso() });

  if (decision === "skip") {
    prospects.updateProspect(email, { status: "skipped" });
    prospects.log({ email, mailveri_status: result.status, decision: "skipped" });
    return;
  }
  if (decision === "review") {
    prospects.updateProspect(email, { status: "needs_review" });
    prospects.log({
      email, mailveri_status: result.status, decision: "needs_review",
      note: "set status back to 'queued' to send after review",
    });
    return;
  }

  const { subject, body } = compose(p);
  if (DRY_RUN) {
    console.log(`    (dry run) would send: ${subject}`);
    prospects.updateProspect(email, { status: "dry_run" });
    prospects.log({ email, mailveri_status: result.status, decision: "dry_run", note: subject });
    return;
  }

  const sent = await agentmail.inboxes.messages.send(inbox.inboxId, {
    to: [email],
    subject,
    text: body,
    labels: ["outreach", `mailveri-${result.status.toLowerCase().replace(/_/g, "-")}`],
  });
  console.log(`    ✉  sent (thread ${sent.threadId})`);
  prospects.updateProspect(email, { status: "sent", sent_at: prospects.nowIso(), thread_id: sent.threadId });
  prospects.log({ email, mailveri_status: result.status, decision: "sent", thread_id: sent.threadId, note: subject });
}

// --- main --------------------------------------------------------------------

async function main(): Promise<void> {
  const queue = prospects.queuedProspects();
  if (!queue.length) { console.log("No queued prospects in prospects.csv."); return; }

  const inbox = DRY_RUN ? null : await getOrCreateInbox();
  console.log(`📬 Sending from: ${inbox ? inbox.email : "(dry run, nothing will be sent)"}`);
  console.log(
    `   ${queue.length} queued | role accounts: ${SEND_ROLE_ACCOUNTS ? "send" : "review"}` +
    ` | catch-all: ${SEND_CATCH_ALL ? "send" : "review"}`,
  );

  for (const [i, p] of queue.entries()) {
    if (i) await sleep(VERIFY_INTERVAL_MS);
    try {
      await processProspect(p, inbox);
    } catch (e: any) {
      if (e instanceof mailveri.MailVeriError) {
        console.log(`\n✋ Stopping: ${e.message}. Remaining prospects stay queued.`);
        return;
      }
      console.log(`    ! failed for ${p.email}: ${e.message}`);
    }
  }
  console.log("\nDone. See prospects.csv for status and verify_log.csv for the audit log.");
}

main().catch((e) => { console.error(e); process.exit(1); });
