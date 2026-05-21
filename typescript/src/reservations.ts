/**
 * JSON-backed state for tracking active reservation requests.
 */

import * as fs from "node:fs";

const STATE_FILE = "reservations.json";

export interface Reservation {
  id: string;
  status: string;
  created_at: string;
  updated_at?: string;
  restaurant_email?: string;
  restaurant_name?: string;
  restaurant_thread_id?: string;
  user_thread_id?: string;
  details?: any;
  alternative?: string;
}

interface Store {
  reservations: Record<string, Reservation>;
}

function load(): Store {
  if (!fs.existsSync(STATE_FILE)) return { reservations: {} };
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
  } catch {
    return { reservations: {} };
  }
}

function save(state: Store): void {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

export function upsert(id: string, fields: Partial<Reservation>): Reservation {
  const state = load();
  const existing = state.reservations[id] || {
    id,
    status: "new",
    created_at: new Date().toISOString(),
  };
  const updated: Reservation = {
    ...existing,
    ...fields,
    id,
    updated_at: new Date().toISOString(),
  };
  state.reservations[id] = updated;
  save(state);
  return updated;
}

export function findByRestaurantThread(threadId: string): Reservation | undefined {
  const state = load();
  for (const r of Object.values(state.reservations)) {
    if (r.restaurant_thread_id === threadId) return r;
  }
  return undefined;
}

export function findByUserThread(threadId: string): Reservation | undefined {
  const state = load();
  for (const r of Object.values(state.reservations)) {
    if (r.user_thread_id === threadId) return r;
  }
  return undefined;
}
