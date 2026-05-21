/**
 * vendors.csv — allowlist of vendors approved for autonomous payment.
 */

import { existsSync, readFileSync } from "node:fs";

const FILE = "vendors.csv";

export interface Vendor {
  vendor_name: string;
  vendor_email: string;
  max_amount_usd: number;
  notes: string;
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

export function load(): Vendor[] {
  if (!existsSync(FILE)) return [];
  const lines = readFileSync(FILE, "utf-8").split("\n").filter(l => l.length > 0);
  if (lines.length < 2) return [];
  const headers = parseLine(lines[0]);
  return lines.slice(1).map(line => {
    const fields = parseLine(line);
    const row: any = {};
    headers.forEach((h, i) => row[h] = fields[i] ?? "");
    return {
      vendor_name: (row.vendor_name || "").trim(),
      vendor_email: (row.vendor_email || "").trim().toLowerCase(),
      max_amount_usd: parseFloat(row.max_amount_usd) || 0,
      notes: (row.notes || "").trim(),
    } as Vendor;
  });
}

export function find(vendors: Vendor[], senderEmail: string): Vendor | null {
  if (!senderEmail) return null;
  const target = senderEmail.toLowerCase().trim();
  return vendors.find(v => v.vendor_email === target) ?? null;
}
