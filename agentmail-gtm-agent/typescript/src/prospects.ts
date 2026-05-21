/**
 * CSV-backed prospect tracker + audit log.
 */

import * as fs from "node:fs";

const PROSPECTS_FILE = "prospects.csv";
const LOG_FILE = "gtm_log.csv";

const COLUMNS = [
  "email", "name", "role", "company", "hook",
  "status", "first_touch_at", "followup_at",
  "replied_at", "classification", "thread_id",
] as const;

const LOG_COLUMNS = [
  "timestamp_utc", "action", "prospect_email", "classification",
  "thread_id", "note",
] as const;

export interface Prospect {
  email: string;
  name: string;
  role: string;
  company: string;
  hook: string;
  status: string;
  first_touch_at: string;
  followup_at: string;
  replied_at: string;
  classification: string;
  thread_id: string;
}

// --- CSV parsing helpers (RFC 4180 minimal) ---------------------------------

function csvEscape(s: string): string {
  if (s == null) return "";
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inQuotes) {
      if (c === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (c === '"') inQuotes = false;
      else cur += c;
    } else {
      if (c === '"') inQuotes = true;
      else if (c === ",") { out.push(cur); cur = ""; }
      else cur += c;
    }
  }
  out.push(cur);
  return out;
}

function readCsv(path: string): Record<string, string>[] {
  if (!fs.existsSync(path)) return [];
  const text = fs.readFileSync(path, "utf8");
  const lines = text.split(/\r?\n/).filter((l) => l.length);
  if (!lines.length) return [];
  const headers = parseCsvLine(lines[0]);
  const rows: Record<string, string>[] = [];
  for (let i = 1; i < lines.length; i++) {
    const cells = parseCsvLine(lines[i]);
    const row: Record<string, string> = {};
    headers.forEach((h, idx) => { row[h] = (cells[idx] ?? "").trim(); });
    rows.push(row);
  }
  return rows;
}

function writeCsv(path: string, rows: Record<string, string>[], columns: readonly string[]): void {
  const header = columns.join(",");
  const body = rows.map((r) => columns.map((c) => csvEscape(r[c] ?? "")).join(",")).join("\n");
  fs.writeFileSync(path, header + "\n" + (body ? body + "\n" : ""));
}

function normalize(row: Record<string, string>): Prospect {
  const out: any = {};
  for (const c of COLUMNS) out[c] = (row[c] ?? "").trim();
  return out as Prospect;
}

// --- prospects --------------------------------------------------------------

export function loadAll(): Prospect[] {
  return readCsv(PROSPECTS_FILE).map(normalize);
}

export function saveAll(rows: Prospect[]): void {
  writeCsv(PROSPECTS_FILE, rows as any, COLUMNS);
}

export function updateProspect(email: string, fields: Partial<Prospect>): Prospect | undefined {
  const rows = loadAll();
  let target: Prospect | undefined;
  for (const r of rows) {
    if (r.email.toLowerCase() === email.toLowerCase()) {
      Object.assign(r, fields);
      target = r;
      break;
    }
  }
  if (target) saveAll(rows);
  return target;
}

export function findByThread(threadId: string): Prospect | undefined {
  return loadAll().find((r) => r.thread_id === threadId);
}

export function queuedProspects(): Prospect[] {
  return loadAll().filter((r) => r.status === "" || r.status === "queued");
}

export function followupsDue(afterHours: number): Prospect[] {
  const cutoff = Date.now() - afterHours * 3600 * 1000;
  return loadAll().filter((r) => {
    if (r.status !== "first_touch_sent") return false;
    if (!r.first_touch_at) return false;
    const ts = new Date(r.first_touch_at).getTime();
    return !isNaN(ts) && ts <= cutoff;
  });
}

// --- log --------------------------------------------------------------------

function ensureLogHeader(): void {
  if (!fs.existsSync(LOG_FILE) || fs.statSync(LOG_FILE).size === 0) {
    fs.writeFileSync(LOG_FILE, LOG_COLUMNS.join(",") + "\n");
  }
}

export function logAction(opts: {
  action: string;
  prospect_email: string;
  classification?: string;
  thread_id?: string;
  note?: string;
}): void {
  ensureLogHeader();
  const row = [
    new Date().toISOString(),
    opts.action,
    opts.prospect_email,
    opts.classification || "",
    opts.thread_id || "",
    (opts.note || "").replace(/\n/g, " ").slice(0, 500),
  ].map(csvEscape).join(",");
  fs.appendFileSync(LOG_FILE, row + "\n");
}
