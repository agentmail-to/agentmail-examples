/**
 * CSV-backed open purchase order list.
 *
 * `purchase_orders.csv` columns:
 *   po_number, vendor_name, amount, currency, description, status
 *
 * Match priority:
 *   1. Exact PO number (best signal — invoice cites the PO)
 *   2. Vendor name + amount within $1 (fallback for invoices missing PO ref)
 */

import * as fs from "node:fs";

const PO_FILE = "purchase_orders.csv";

export interface PurchaseOrder {
  po_number: string;
  vendor_name: string;
  amount: string; // CSV stores as string
  currency: string;
  description: string;
  status: string;
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

export function loadAll(): PurchaseOrder[] {
  if (!fs.existsSync(PO_FILE)) return [];
  const text = fs.readFileSync(PO_FILE, "utf8");
  const lines = text.split(/\r?\n/).filter((l) => l.length);
  if (!lines.length) return [];
  const headers = parseCsvLine(lines[0]);
  const rows: PurchaseOrder[] = [];
  for (let i = 1; i < lines.length; i++) {
    const cells = parseCsvLine(lines[i]);
    const row: any = {};
    headers.forEach((h, idx) => { row[h] = (cells[idx] ?? "").trim(); });
    rows.push(row as PurchaseOrder);
  }
  return rows;
}

export function findMatch(
  poNumber: string | null,
  vendorName: string | null,
  amount: number | null,
): PurchaseOrder | undefined {
  const rows = loadAll().filter(
    (r) => (r.status || "open").toLowerCase() === "open",
  );

  // Strategy 1: exact PO number match
  if (poNumber) {
    const poClean = poNumber.trim().toUpperCase();
    const m = rows.find((r) => (r.po_number || "").trim().toUpperCase() === poClean);
    if (m) return m;
  }

  // Strategy 2: vendor name + amount within $1
  if (vendorName && amount !== null && !isNaN(amount)) {
    const vClean = vendorName.trim().toLowerCase();
    for (const r of rows) {
      const vMatch = (r.vendor_name || "").trim().toLowerCase() === vClean;
      const rAmount = parseFloat(r.amount || "0");
      const aMatch = !isNaN(rAmount) && Math.abs(rAmount - amount) <= 1.0;
      if (vMatch && aMatch) return r;
    }
  }

  return undefined;
}
