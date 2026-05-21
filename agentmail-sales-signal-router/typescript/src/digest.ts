/**
 * End-of-day digest builder + dedupe state.
 */

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import * as signals from "./signals.js";
import * as slack from "./slack.js";

const STATE = ".last_digest";

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

function alreadySentToday(): boolean {
  if (!existsSync(STATE)) return false;
  return readFileSync(STATE, "utf-8").trim() === todayStr();
}

function markSentToday(): void {
  writeFileSync(STATE, todayStr());
}

const PRIORITY: Record<string, number> = {
  positive: 0, objection: 1, unsubscribe: 2, ooo: 3,
};

export function buildText(rows: Record<string, string>[]): string {
  if (rows.length === 0) {
    return `:calendar: *EOD signals digest* — no signals today.`;
  }

  const byClass: Record<string, Record<string, string>[]> = {};
  for (const r of rows) {
    (byClass[r.classification] ??= []).push(r);
  }

  const hot = byClass.hot_reply ?? [];
  const crm = byClass.crm_notification ?? [];
  const watch = byClass.watchlist_match ?? [];
  const noise = byClass.noise ?? [];

  const totalAmount = crm.reduce((sum, r) => sum + (parseFloat(r.amount_usd) || 0), 0);

  const dateLabel = new Date().toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });
  const lines = [
    `:calendar: *EOD signals digest* — ${dateLabel}`,
    "",
    `• Hot replies: ${hot.length}   • CRM events: ${crm.length}   ` +
      `• Watchlist hits: ${watch.length}   • Noise: ${noise.length}`,
  ];
  if (totalAmount) {
    lines.push(`• Total deal volume from CRM events: $${totalAmount.toLocaleString()}`);
  }

  if (hot.length) {
    lines.push("", "*Top hot replies:*");
    const sorted = [...hot].sort((a, b) =>
      (PRIORITY[a.sentiment_or_event] ?? 9) - (PRIORITY[b.sentiment_or_event] ?? 9)
    );
    for (const r of sorted.slice(0, 5)) {
      lines.push(`  • [${r.sentiment_or_event || "?"}] ${r.sender} — ${r.summary}`);
    }
  }

  if (crm.length) {
    lines.push("", "*CRM events:*");
    const sorted = [...crm].sort((a, b) => (parseFloat(b.amount_usd) || 0) - (parseFloat(a.amount_usd) || 0));
    for (const r of sorted.slice(0, 5)) {
      const amt = parseFloat(r.amount_usd) || 0;
      const amtStr = amt ? `$${amt.toLocaleString()}` : "";
      lines.push(`  • ${r.sentiment_or_event}: ${r.customer} ${amtStr} — ${r.summary}`);
    }
  }

  if (watch.length) {
    lines.push("", "*Watchlist hits:*");
    for (const r of watch.slice(0, 5)) {
      lines.push(`  • ${r.sender} (${r.sentiment_or_event}) — ${r.summary}`);
    }
  }

  return lines.join("\n");
}

export async function maybeSend(opts: {
  agentmail: any;
  inbox: any;
  salesLeadEmail: string;
  hour: number;
}): Promise<void> {
  const now = new Date();
  if (now.getHours() < opts.hour) return;
  if (alreadySentToday()) return;

  const rows = signals.readToday();
  const text = buildText(rows);

  // Slack
  await slack.digest(text);
  console.log(`  ✓ digest posted to Slack (${rows.length} signals)`);

  // Email
  if (opts.salesLeadEmail) {
    try {
      await opts.agentmail.inboxes.messages.send(opts.inbox.inboxId, {
        to: [opts.salesLeadEmail],
        subject: `[Sales signals] EOD digest — ${now.toLocaleDateString("en-US", { month: "short", day: "numeric" })} — ${rows.length} signals`,
        text,
      });
      console.log(`  ✓ digest emailed to ${opts.salesLeadEmail}`);
    } catch (e: any) {
      console.warn(`  ! couldn't email digest: ${e.message}`);
    }
  }

  markSentToday();
}
