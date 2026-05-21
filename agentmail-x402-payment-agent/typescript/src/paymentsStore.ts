/**
 * payments.csv — append-only audit ledger.
 */

import { existsSync, appendFileSync, readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";

const FILE = "payments.csv";
const HEADER = [
  "id", "vendor_name", "vendor_email", "amount", "currency", "status",
  "transaction_id", "invoice_number", "decision", "decided_at",
  "source_message_id", "created",
];

function ensureHeader(): void {
  if (!existsSync(FILE)) writeFileSync(FILE, HEADER.join(",") + "\n");
}

function escapeCsv(v: string): string {
  if (v.includes(",") || v.includes('"') || v.includes("\n")) {
    return `"${v.replace(/"/g, '""')}"`;
  }
  return v;
}

function parseLine(line: string): string[] {
  const out: string[] = [];
  let cur = "", inQuote = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inQuote) {
      if (c === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (c === '"') inQuote = false;
      else cur += c;
    } else {
      if (c === '"') inQuote = true;
      else if (c === ",") { out.push(cur); cur = ""; }
      else cur += c;
    }
  }
  out.push(cur);
  return out;
}

function paymentId(invoiceNumber: string, vendorEmail: string, amount: number): string {
  return createHash("sha1")
    .update(`${invoiceNumber}|${vendorEmail}|${amount.toFixed(2)}`)
    .digest("hex").slice(0, 12);
}

export interface PaymentRow {
  id: string;
  vendor_name: string;
  vendor_email: string;
  amount: string;
  currency: string;
  status: string;
  transaction_id: string;
  invoice_number: string;
  decision: string;
  decided_at: string;
  source_message_id: string;
  created: string;
}

function readAll(): PaymentRow[] {
  if (!existsSync(FILE)) return [];
  const lines = readFileSync(FILE, "utf-8").split("\n").filter(l => l.length > 0);
  if (lines.length < 2) return [];
  const headers = parseLine(lines[0]);
  return lines.slice(1).map(line => {
    const fields = parseLine(line);
    const row: any = {};
    headers.forEach((h, i) => row[h] = fields[i] ?? "");
    return row as PaymentRow;
  });
}

function writeAll(rows: PaymentRow[]): void {
  ensureHeader();
  const lines = [HEADER.join(",")];
  for (const r of rows) {
    lines.push(HEADER.map(h => escapeCsv(String((r as any)[h] ?? ""))).join(","));
  }
  writeFileSync(FILE, lines.join("\n") + "\n");
}

export function isDuplicate(invoiceNumber: string, vendorEmail: string): boolean {
  if (!invoiceNumber) return false;
  return readAll().some(r =>
    r.invoice_number === invoiceNumber &&
    r.vendor_email.toLowerCase() === vendorEmail.toLowerCase()
  );
}

export function append(args: {
  vendorName: string; vendorEmail: string; amount: number; currency: string;
  invoiceNumber: string; decision: string; status: string;
  transactionId?: string; sourceMessageId?: string;
}): PaymentRow {
  ensureHeader();
  const pid = paymentId(args.invoiceNumber || args.sourceMessageId || "", args.vendorEmail, args.amount);
  const row: PaymentRow = {
    id: pid,
    vendor_name: args.vendorName,
    vendor_email: args.vendorEmail.toLowerCase(),
    amount: args.amount.toFixed(2),
    currency: args.currency,
    status: args.status,
    transaction_id: args.transactionId ?? "",
    invoice_number: args.invoiceNumber,
    decision: args.decision,
    decided_at: ["paid", "failed"].includes(args.status) ? new Date().toISOString().slice(0, 19) + "+00:00" : "",
    source_message_id: args.sourceMessageId ?? "",
    created: new Date().toISOString().slice(0, 19) + "+00:00",
  };
  appendFileSync(FILE, HEADER.map(h => escapeCsv(String((row as any)[h] ?? ""))).join(",") + "\n");
  return row;
}

export function updateStatus(id: string, status: string, transactionId = "", decision = ""): boolean {
  const rows = readAll();
  let n = 0;
  for (const r of rows) {
    if (r.id === id) {
      r.status = status;
      if (transactionId) r.transaction_id = transactionId;
      if (decision) r.decision = decision;
      r.decided_at = new Date().toISOString().slice(0, 19) + "+00:00";
      n++;
    }
  }
  if (n) writeAll(rows);
  return n > 0;
}

export function findPendingInThreadIds(messageIdsInThread: Set<string>): PaymentRow | null {
  const rows = readAll();
  for (let i = rows.length - 1; i >= 0; i--) {
    if (rows[i].status === "pending_review" && messageIdsInThread.has(rows[i].source_message_id)) {
      return rows[i];
    }
  }
  return null;
}
