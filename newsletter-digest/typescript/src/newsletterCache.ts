/**
 * JSON-backed cache of summarized newsletter items.
 */

import * as fs from "node:fs";

const CACHE_FILE = "newsletter_cache.json";
const RETENTION_DAYS = 14;

export interface CacheItem {
  date_iso: string;
  headline: string;
  key_points: string;
  primary_link: string;
  topic: string;
  importance: number;
  source_subject: string;
  source_from: string;
  source_message_id: string;
}

interface Cache {
  items: CacheItem[];
}

function load(): Cache {
  if (!fs.existsSync(CACHE_FILE)) return { items: [] };
  try {
    return JSON.parse(fs.readFileSync(CACHE_FILE, "utf8"));
  } catch {
    return { items: [] };
  }
}

function save(state: Cache): void {
  fs.writeFileSync(CACHE_FILE, JSON.stringify(state, null, 2));
}

function trim(state: Cache): void {
  const cutoff = Date.now() - RETENTION_DAYS * 24 * 60 * 60 * 1000;
  state.items = state.items.filter(
    (i) => new Date(i.date_iso).getTime() >= cutoff,
  );
}

export function appendItem(item: CacheItem): void {
  const state = load();
  state.items.push(item);
  trim(state);
  save(state);
}

export function getRecentItems(hours = 24): CacheItem[] {
  const state = load();
  const cutoff = Date.now() - hours * 60 * 60 * 1000;
  return state.items.filter(
    (i) => new Date(i.date_iso).getTime() >= cutoff,
  );
}

export function clearRecent(items: CacheItem[]): void {
  const state = load();
  const ids = new Set(items.map((i) => i.source_message_id));
  state.items = state.items.filter((i) => !ids.has(i.source_message_id));
  save(state);
}
