/**
 * CSV-backed prospect list + verify_log.csv audit log.
 *
 * `status` moves through: queued -> sent | skipped | needs_review | dry_run.
 * Rows with status empty or 'queued' are picked up on the next run. To retry a
 * row (for example after reviewing a CATCH_ALL), set its status back to 'queued'.
 */

import * as fs from "node:fs";

const PROSPECTS_FILE = "prospects.csv";
const LOG_FILE = "verify_log.csv";

const COLUMNS = [
  "email", "name", "company", "hook",
  "status", "verify_status", "verified_at", "sent_at", "thread_id",
] as const;

const LOG_COLUMNS = ["timestamp_utc", "email", "mailveri_status", "decision", "thread_id", "note"] as const;

export type Prospect = Record<(typeof COLUMNS)[number], string>;

export const nowIso = () => new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00");

// --- CSV helpers (RFC 4180 minimal) ----------------------------------------

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

// --- prospects --------------------------------------------------------------

export function loadAll(): Prospect[] {
  if (!fs.existsSync(PROSPECTS_FILE)) return [];
  const lines = fs.readFileSync(PROSPECTS_FILE, "utf8").split(/\r?\n/).filter((l) => l.length);
  if (!lines.length) return [];
  const headers = parseCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const cells = parseCsvLine(line);
    const raw: Record<string, string> = {};
    headers.forEach((h, i) => { raw[h] = cells[i] ?? ""; });
    const row: any = {};
    for (const c of COLUMNS) row[c] = (raw[c] ?? "").trim();
    return row as Prospect;
  });
}

export function saveAll(rows: Prospect[]): void {
  const body = rows.map((r) => COLUMNS.map((c) => csvEscape(r[c] ?? "")).join(",")).join("\n");
  fs.writeFileSync(PROSPECTS_FILE, COLUMNS.join(",") + "\n" + (body ? body + "\n" : ""));
}

export function updateProspect(email: string, fields: Partial<Prospect>): void {
  const rows = loadAll();
  const target = rows.find((r) => r.email.toLowerCase() === email.toLowerCase());
  if (target) { Object.assign(target, fields); saveAll(rows); }
}

export function queuedProspects(): Prospect[] {
  return loadAll().filter((r) => r.email && (r.status === "" || r.status === "queued"));
}

// --- log --------------------------------------------------------------------

export function log(entry: {
  email: string; mailveri_status: string; decision: string; thread_id?: string; note?: string;
}): void {
  if (!fs.existsSync(LOG_FILE) || fs.statSync(LOG_FILE).size === 0) {
    fs.writeFileSync(LOG_FILE, LOG_COLUMNS.join(",") + "\n");
  }
  const row = [
    nowIso(), entry.email, entry.mailveri_status, entry.decision,
    entry.thread_id ?? "", (entry.note ?? "").replace(/\n/g, " ").slice(0, 500),
  ];
  fs.appendFileSync(LOG_FILE, row.map(csvEscape).join(",") + "\n");
}
