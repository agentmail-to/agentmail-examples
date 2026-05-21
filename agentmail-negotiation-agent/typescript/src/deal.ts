/**
 * JSON-backed deal + counterparty state.
 */

import * as fs from "node:fs";

const DEAL_FILE = "deal.json";

export interface CounterpartyOffer {
  price: number;
  currency: string;
  terms_summary: string;
  meets_must_haves: boolean;
  notes: string;
  received_at?: string;
}

export interface Counterparty {
  email: string;
  name: string;
  status?: "queued" | "contacted" | "offered" | "declined" | "countered" | "target_hit" | "walked";
  thread_id?: string;
  contacted_at?: string;
  last_counter_at?: string;
  last_anchor?: number;
  decline_reason?: string;
  current_offer?: CounterpartyOffer | null;
}

export interface Deal {
  what: string;
  must_haves: string[];
  ideal_price: number;
  max_price: number;
  currency: string;
  deal_context?: string;
  counterparties: Counterparty[];
  buyer_accept_intent?: any[];
}

export function load(): Deal | null {
  if (!fs.existsSync(DEAL_FILE)) return null;
  try {
    return JSON.parse(fs.readFileSync(DEAL_FILE, "utf8")) as Deal;
  } catch {
    return null;
  }
}

export function save(state: Deal): void {
  fs.writeFileSync(DEAL_FILE, JSON.stringify(state, null, 2));
}

export function getCounterpartyByEmail(email: string): Counterparty | undefined {
  const deal = load();
  if (!deal) return undefined;
  return deal.counterparties.find((cp) => cp.email.toLowerCase() === email.toLowerCase());
}

export function getCounterpartyByThread(threadId: string): Counterparty | undefined {
  const deal = load();
  if (!deal) return undefined;
  return deal.counterparties.find((cp) => cp.thread_id === threadId);
}

export function updateCounterparty(
  email: string,
  fields: Partial<Counterparty>,
): Counterparty | undefined {
  const deal = load();
  if (!deal) return undefined;
  let target: Counterparty | undefined;
  for (const cp of deal.counterparties) {
    if (cp.email.toLowerCase() === email.toLowerCase()) {
      Object.assign(cp, fields);
      target = cp;
      break;
    }
  }
  if (target) save(deal);
  return target;
}

export function queuedCounterparties(): Counterparty[] {
  const deal = load();
  if (!deal) return [];
  return deal.counterparties.filter(
    (cp) => !cp.status || cp.status === "queued",
  );
}

export function allReplied(d?: Deal | null): boolean {
  const deal = d ?? load();
  if (!deal || !deal.counterparties.length) return false;
  const terminal = new Set(["offered", "declined", "walked", "target_hit"]);
  return deal.counterparties.every((cp) => terminal.has(cp.status || ""));
}
