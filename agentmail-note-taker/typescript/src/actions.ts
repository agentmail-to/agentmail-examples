/**
 * actions.csv — flat ledger of action items extracted across notes.
 */

import { existsSync, appendFileSync, readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";

const FILE = "actions.csv";
const HEADER = ["id", "note_path", "owner", "task", "deadline", "urgency", "status", "created"];

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

function actionId(notePath: string, owner: string, task: string): string {
  return createHash("sha1").update(`${notePath}|${owner}|${task}`).digest("hex").slice(0, 12);
}

export interface ActionRow {
  id: string;
  note_path: string;
  owner: string;
  task: string;
  deadline: string;
  urgency: string;
  status: string;
  created: string;
}

function readAll(): ActionRow[] {
  if (!existsSync(FILE)) return [];
  const lines = readFileSync(FILE, "utf-8").split("\n").filter(l => l.length > 0);
  if (lines.length < 2) return [];
  const headers = parseLine(lines[0]);
  return lines.slice(1).map(line => {
    const fields = parseLine(line);
    const row: any = {};
    headers.forEach((h, i) => row[h] = fields[i] ?? "");
    return row as ActionRow;
  });
}

function writeAll(rows: ActionRow[]): void {
  ensureHeader();
  const lines = [HEADER.join(",")];
  for (const r of rows) {
    lines.push(HEADER.map(h => escapeCsv(String((r as any)[h] ?? ""))).join(","));
  }
  writeFileSync(FILE, lines.join("\n") + "\n");
}

export function appendFromNote(
  notePath: string,
  actionItems: Array<{ owner?: string; task?: string; deadline?: string; urgency?: string }>,
): ActionRow[] {
  ensureHeader();
  const existing = readAll();
  const existingIds = new Set(existing.map(r => r.id));
  const newRows: ActionRow[] = [];

  for (const ai of actionItems) {
    const owner = (ai.owner || "").trim();
    const task = (ai.task || "").trim();
    if (!task) continue;
    const id = actionId(notePath, owner, task);
    if (existingIds.has(id)) continue;
    const row: ActionRow = {
      id, note_path: notePath, owner, task,
      deadline: (ai.deadline || "").trim(),
      urgency: (ai.urgency || "").trim(),
      status: "open",
      created: new Date().toISOString().slice(0, 19) + "+00:00",
    };
    newRows.push(row);
    existingIds.add(id);
  }

  if (newRows.length) {
    const csvLines = newRows.map(r =>
      HEADER.map(h => escapeCsv(String((r as any)[h] ?? ""))).join(",")
    );
    appendFileSync(FILE, csvLines.join("\n") + "\n");
  }
  return newRows;
}

export function markDoneForNote(notePath: string): number {
  const rows = readAll();
  let n = 0;
  for (const r of rows) {
    if (r.note_path === notePath && r.status === "open") {
      r.status = "done";
      n++;
    }
  }
  if (n) writeAll(rows);
  return n;
}

export function listOpen(): ActionRow[] {
  return readAll().filter(r => r.status === "open");
}

export function isOverdue(row: ActionRow, today: Date): boolean {
  if (!row.deadline) return false;
  const d = new Date(row.deadline);
  if (isNaN(d.getTime())) return false;
  return d < new Date(today.toISOString().slice(0, 10));
}

export function hoursUntil(row: ActionRow, now: Date): number | null {
  if (!row.deadline) return null;
  let d = new Date(row.deadline);
  if (isNaN(d.getTime())) return null;
  // Date-only deadlines → end of day
  if (d.getUTCHours() === 0 && d.getUTCMinutes() === 0) {
    d = new Date(d.getTime() + (23 * 60 + 59) * 60 * 1000);
  }
  return (d.getTime() - now.getTime()) / 3_600_000;
}
