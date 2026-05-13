/**
 * signals.csv — append-only audit log.
 */

import { existsSync, appendFileSync, readFileSync, writeFileSync } from "node:fs";

const FILE = "signals.csv";
const HEADER = [
  "timestamp", "message_id", "sender", "classification",
  "sentiment_or_event", "amount_usd", "customer", "summary", "slack_fired",
];

function ensureHeader(): void {
  if (!existsSync(FILE)) {
    writeFileSync(FILE, HEADER.join(",") + "\n");
  }
}

function escapeCsv(v: string): string {
  if (v.includes(",") || v.includes('"') || v.includes("\n")) {
    return `"${v.replace(/"/g, '""')}"`;
  }
  return v;
}

export interface SignalLog {
  messageId: string;
  sender: string;
  classification: string;
  sentimentOrEvent?: string;
  amountUsd?: number;
  customer?: string;
  summary?: string;
  slackFired?: boolean;
}

export function log(s: SignalLog): void {
  ensureHeader();
  const row = [
    new Date().toISOString().slice(0, 19) + "+00:00",
    s.messageId,
    s.sender,
    s.classification,
    s.sentimentOrEvent ?? "",
    s.amountUsd ? s.amountUsd.toFixed(2) : "",
    s.customer ?? "",
    (s.summary ?? "").replace(/\n/g, " ").trim().slice(0, 300),
    s.slackFired ? "yes" : "no",
  ].map(v => escapeCsv(String(v)));
  appendFileSync(FILE, row.join(",") + "\n");
}

export function readToday(): Record<string, string>[] {
  if (!existsSync(FILE)) return [];
  const lines = readFileSync(FILE, "utf-8").split("\n").filter(l => l.length > 0);
  if (lines.length < 2) return [];

  const headers = lines[0].split(",");
  const today = new Date().toISOString().slice(0, 10);

  const rows: Record<string, string>[] = [];
  for (let i = 1; i < lines.length; i++) {
    // Simple CSV parse — handles quoted fields
    const fields = parseCsvLine(lines[i]);
    if (fields.length < headers.length) continue;
    const row: Record<string, string> = {};
    headers.forEach((h, j) => row[h] = fields[j] ?? "");
    if (row.timestamp.startsWith(today)) rows.push(row);
  }
  return rows;
}

function parseCsvLine(line: string): string[] {
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
