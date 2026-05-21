/**
 * Watchlist loader — re-reads watchlist.json on every call so live edits
 * take effect without restarting the agent.
 */

import { readFileSync, existsSync } from "node:fs";

export interface Watchlist {
  deal_owners: Record<string, string>;
  watchlist_domains: string[];
  watchlist_keywords: string[];
  crm_notification_senders: string[];
}

const FILE = "watchlist.json";
const EMPTY: Watchlist = {
  deal_owners: {},
  watchlist_domains: [],
  watchlist_keywords: [],
  crm_notification_senders: [],
};

export function load(): Watchlist {
  if (!existsSync(FILE)) return EMPTY;
  try {
    const parsed = JSON.parse(readFileSync(FILE, "utf-8"));
    return {
      deal_owners: parsed.deal_owners ?? {},
      watchlist_domains: parsed.watchlist_domains ?? [],
      watchlist_keywords: parsed.watchlist_keywords ?? [],
      crm_notification_senders: parsed.crm_notification_senders ?? [],
    };
  } catch (e: any) {
    console.warn(`  ! watchlist.json malformed: ${e.message}`);
    return EMPTY;
  }
}

export function contextBlock(wl: Watchlist): string {
  const fmt = (xs: string[]) => xs.length ? xs.join(", ") : "(none)";
  return (
    `Watchlist domains: ${fmt(wl.watchlist_domains)}\n` +
    `Watchlist keywords: ${fmt(wl.watchlist_keywords)}\n` +
    `Known CRM/billing notification senders: ${fmt(wl.crm_notification_senders)}`
  );
}

export function findOwner(wl: Watchlist, senderEmail: string, body: string): string {
  const owners = wl.deal_owners ?? {};
  const domain = senderEmail.includes("@") ? senderEmail.split("@", 2)[1].toLowerCase() : "";
  if (domain && owners[domain]) return owners[domain];

  const bodyLower = body.toLowerCase();
  for (const [d, owner] of Object.entries(owners)) {
    if (d === "_comment") continue;
    if (bodyLower.includes(d.toLowerCase())) return owner;
  }
  return "";
}
