/**
 * Processed-invoice tracker (for duplicate detection) + audit log.
 *
 * Two files:
 *   invoices.json  — { "processed": [{invoice_number, vendor, ...}] }
 *   invoice_log.csv — append-only ledger of every action.
 */

import * as fs from "node:fs";

const PROCESSED_FILE = "invoices.json";
const LOG_FILE = "invoice_log.csv";

const LOG_COLUMNS = [
  "timestamp_utc", "action", "vendor", "invoice_number",
  "amount", "currency", "due_date", "po_number", "status",
  "thread_id", "note",
] as const;

interface Processed {
  recorded_at: string;
  vendor: string;
  invoice_number: string;
  amount: number;
  currency: string;
  due_date: string;
  po_number: string;
  po_match: string;
  status: string;
  is_urgent: boolean;
  message_id: string;
  thread_id: string;
}

function loadProcessed(): { processed: Processed[] } {
  if (!fs.existsSync(PROCESSED_FILE)) return { processed: [] };
  try {
    return JSON.parse(fs.readFileSync(PROCESSED_FILE, "utf8"));
  } catch {
    return { processed: [] };
  }
}

function saveProcessed(state: { processed: Processed[] }): void {
  fs.writeFileSync(PROCESSED_FILE, JSON.stringify(state, null, 2));
}

export function isDuplicate(invoiceNumber: string, vendor: string = ""): boolean {
  if (!invoiceNumber) return false;
  const state = loadProcessed();
  const invClean = invoiceNumber.trim();
  const vClean = (vendor || "").trim().toLowerCase();
  for (const p of state.processed) {
    if ((p.invoice_number || "").trim() === invClean) {
      if (!vClean || (p.vendor || "").trim().toLowerCase() === vClean) {
        return true;
      }
    }
  }
  return false;
}

export function recordProcessed(invoice: Omit<Processed, "recorded_at">): void {
  const state = loadProcessed();
  state.processed.push({
    recorded_at: new Date().toISOString(),
    ...invoice,
  });
  saveProcessed(state);
}

function csvEscape(s: string): string {
  if (s == null) return "";
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function ensureLogHeader(): void {
  if (!fs.existsSync(LOG_FILE) || fs.statSync(LOG_FILE).size === 0) {
    fs.writeFileSync(LOG_FILE, LOG_COLUMNS.join(",") + "\n");
  }
}

export function logAction(opts: {
  action: string;
  vendor?: string;
  invoice_number?: string;
  amount?: string;
  currency?: string;
  due_date?: string;
  po_number?: string;
  status?: string;
  thread_id?: string;
  note?: string;
}): void {
  ensureLogHeader();
  const row = [
    new Date().toISOString(),
    opts.action,
    opts.vendor || "",
    opts.invoice_number || "",
    opts.amount || "",
    opts.currency || "",
    opts.due_date || "",
    opts.po_number || "",
    opts.status || "",
    opts.thread_id || "",
    (opts.note || "").replace(/\n/g, " ").slice(0, 500),
  ].map(csvEscape).join(",");
  fs.appendFileSync(LOG_FILE, row + "\n");
}
