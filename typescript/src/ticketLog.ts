/**
 * Lightweight CSV ticket log.
 *
 * Appends one row per agent action. Lets the support manager grep, sort, or
 * import to a spreadsheet without standing up a database.
 *
 * Columns: timestamp_utc, action, classification, sender, subject, message_id,
 *          thread_id, note
 */

import * as fs from "node:fs";

const LOG_FILE = "tickets.csv";

const COLUMNS = [
  "timestamp_utc",
  "action",
  "classification",
  "sender",
  "subject",
  "message_id",
  "thread_id",
  "note",
];

function csvEscape(s: string): string {
  if (s == null) return "";
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function ensureHeader(): void {
  if (!fs.existsSync(LOG_FILE) || fs.statSync(LOG_FILE).size === 0) {
    fs.writeFileSync(LOG_FILE, COLUMNS.join(",") + "\n");
  }
}

export function logTicket(opts: {
  action: string; // responded | escalated | closed | followed_up
  classification: string;
  sender: string;
  subject: string;
  messageId: string;
  threadId: string;
  note?: string;
}): void {
  ensureHeader();
  const row = [
    new Date().toISOString(),
    opts.action,
    opts.classification,
    opts.sender,
    (opts.subject || "").replace(/\n/g, " ").slice(0, 200),
    opts.messageId,
    opts.threadId,
    (opts.note || "").replace(/\n/g, " ").slice(0, 500),
  ]
    .map(csvEscape)
    .join(",");
  fs.appendFileSync(LOG_FILE, row + "\n");
}
