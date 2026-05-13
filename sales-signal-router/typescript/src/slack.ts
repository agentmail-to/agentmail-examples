/**
 * Slack incoming-webhook fan-out.
 */

type Flow = "default" | "hot" | "enterprise" | "digest";

function urlFor(flow: Flow): string {
  const envKey = {
    hot: "SLACK_WEBHOOK_HOT",
    enterprise: "SLACK_WEBHOOK_ENTERPRISE",
    digest: "SLACK_WEBHOOK_DIGEST",
    default: "",
  }[flow];
  return (envKey && process.env[envKey]) || process.env.SLACK_WEBHOOK_URL || "";
}

async function post(url: string, payload: object): Promise<boolean> {
  if (!url) return false;
  try {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await r.text();
    return body.trim() === "ok";
  } catch (e: any) {
    console.warn(`  ! slack post failed: ${e.message}`);
    return false;
  }
}

export async function hotReplyAlert(args: {
  sender: string;
  summary: string;
  sentiment: string;
  dealOwnerSlackId: string;
  threadUrl?: string;
}): Promise<boolean> {
  const mention = args.dealOwnerSlackId ? `<@${args.dealOwnerSlackId}> ` : "";
  const emoji = ({
    positive: ":fire:",
    objection: ":warning:",
    unsubscribe: ":no_entry:",
    ooo: ":zzz:",
  } as Record<string, string>)[args.sentiment] || ":envelope:";
  let text = `${emoji} *Hot reply* (${args.sentiment}) from \`${args.sender}\`\n${mention}${args.summary}`;
  if (args.threadUrl) text += `\n<${args.threadUrl}|Open thread>`;
  return post(urlFor("hot"), { text });
}

export async function crmEventAlert(args: {
  sender: string;
  eventType: string;
  customer: string;
  dealSizeUsd: number;
  tier: "enterprise" | "mid_market" | "smb";
  summary: string;
}): Promise<boolean> {
  const url = args.tier === "enterprise" ? urlFor("enterprise") : urlFor("default");
  const emoji = ({
    enterprise: ":rocket:",
    mid_market: ":chart_with_upwards_trend:",
    smb: ":seedling:",
  } as Record<string, string>)[args.tier] || ":bell:";
  const amount = args.dealSizeUsd ? `$${args.dealSizeUsd.toLocaleString()}` : "(amount n/a)";
  const eventLabel = args.eventType.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  const text = (
    `${emoji} *${eventLabel}* — ${args.customer || "unknown customer"} (${args.tier})\n` +
    `Amount: ${amount}  ·  Source: \`${args.sender}\`\n` +
    `${args.summary}`
  );
  return post(url, { text });
}

export async function watchlistAlert(args: {
  sender: string;
  matchedTerm: string;
  why: string;
  summary: string;
}): Promise<boolean> {
  const text = (
    `:eyes: *Watchlist match* on \`${args.matchedTerm}\` from \`${args.sender}\`\n` +
    `_${args.why}_\n${args.summary}`
  );
  return post(urlFor("default"), { text });
}

export async function digest(blocksText: string): Promise<boolean> {
  return post(urlFor("digest"), { text: blocksText });
}
