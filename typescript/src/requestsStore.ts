/**
 * requests.csv — append-only ledger.
 */

import { existsSync, appendFileSync, readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";

const FILE = "requests.csv";
const HEADER = [
  "id", "thread_id", "type", "status", "summary", "fields_json",
  "source_message_id", "source_sender", "created", "decided_at", "decided_text",
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

function requestId(threadId: string, sourceMessageId: string): string {
  return createHash("sha1").update(`${threadId}|${sourceMessageId}`).digest("hex").slice(0, 12);
}

export interface RequestRow {
  id: string;
  thread_id: string;
  type: string;
  status: string;
  summary: string;
  fields_json: string;
  source_message_id: string;
  source_sender: string;
  created: string;
  decided_at: string;
  decided_text: string;
}

function readAll(): RequestRow[] {
  if (!existsSync(FILE)) return [];
  const lines = readFileSync(FILE, "utf-8").split("\n").filter(l => l.length > 0);
  if (lines.length < 2) return [];
  const headers = parseLine(lines[0]);
  return lines.slice(1).map(line => {
    const fields = parseLine(line);
    const row: any = {};
    headers.forEach((h, i) => row[h] = fields[i] ?? "");
    return row as RequestRow;
  });
}

function writeAll(rows: RequestRow[]): void {
  ensureHeader();
  const lines = [HEADER.join(",")];
  for (const r of rows) {
    lines.push(HEADER.map(h => escapeCsv(String((r as any)[h] ?? ""))).join(","));
  }
  writeFileSync(FILE, lines.join("\n") + "\n");
}

export function append(args: {
  threadId: string;
  type: string;
  summary: string;
  fields: Record<string, any>;
  sourceMessageId: string;
  sourceSender: string;
}): RequestRow {
  ensureHeader();
  const row: RequestRow = {
    id: requestId(args.threadId, args.sourceMessageId),
    thread_id: args.threadId,
    type: args.type,
    status: "pending",
    summary: args.summary,
    fields_json: JSON.stringify(args.fields),
    source_message_id: args.sourceMessageId,
    source_sender: args.sourceSender,
    created: new Date().toISOString().slice(0, 19) + "+00:00",
    decided_at: "",
    decided_text: "",
  };
  const csvLine = HEADER.map(h => escapeCsv(String((row as any)[h] ?? ""))).join(",");
  appendFileSync(FILE, csvLine + "\n");
  return row;
}

export function findPendingByThread(threadId: string): RequestRow | null {
  if (!threadId) return null;
  const rows = readAll();
  for (let i = rows.length - 1; i >= 0; i--) {
    if (rows[i].thread_id === threadId && rows[i].status === "pending") return rows[i];
  }
  return null;
}

export function updateStatus(requestId: string, newStatus: string, decidedText = ""): boolean {
  const rows = readAll();
  let n = 0;
  for (const r of rows) {
    if (r.id === requestId) {
      r.status = newStatus;
      r.decided_at = new Date().toISOString().slice(0, 19) + "+00:00";
      r.decided_text = decidedText;
      n++;
    }
  }
  if (n) writeAll(rows);
  return n > 0;
}
