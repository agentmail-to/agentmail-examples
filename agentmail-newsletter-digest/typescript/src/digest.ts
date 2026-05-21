/**
 * Build and send the daily digest.
 */

import type { AgentMailClient } from "agentmail";
import type Anthropic from "@anthropic-ai/sdk";
import { getRecentItems, clearRecent, type CacheItem } from "./newsletterCache.js";
import { buildDigestPrompt } from "./prompt.js";

const COMPOSE_DIGEST_TOOL = {
  name: "compose_digest",
  description:
    "Call this with the final, formatted digest email body. Should include " +
    "a greeting, top 5-8 deduped + ranked items with links, and a signoff.",
  input_schema: {
    type: "object" as const,
    required: ["body", "subject"],
    properties: {
      subject: {
        type: "string",
        description: "Email subject line. Keep it short and dated.",
      },
      body: {
        type: "string",
        description: "The plain-text digest body in the format described in the system prompt.",
      },
    },
  },
};

const SKIP_DIGEST_TOOL = {
  name: "skip_digest",
  description: "Call this when there's nothing worth digesting. No email will be sent.",
  input_schema: {
    type: "object" as const,
    required: ["reason"],
    properties: { reason: { type: "string" } },
  },
};

function itemsAsUserMessage(items: CacheItem[]): string {
  return (
    `Here are ${items.length} newsletter items collected over the last 24 hours:\n\n` +
    "```json\n" +
    JSON.stringify(items, null, 2) +
    "\n```\n\n" +
    "Compose the digest now."
  );
}

export function isDigestDue(
  digestTimeStr: string,
  lastDigestDate: string | undefined,
): boolean {
  let wakeH = 8;
  let wakeM = 0;
  try {
    const [h, m] = digestTimeStr.trim().split(":");
    wakeH = parseInt(h, 10);
    wakeM = parseInt(m, 10);
  } catch {
    /* fallback */
  }
  const now = new Date();
  const todayStr = now.toISOString().slice(0, 10);
  if (lastDigestDate === todayStr) return false;
  return now.getHours() > wakeH || (now.getHours() === wakeH && now.getMinutes() >= wakeM);
}

export async function sendDigest(opts: {
  claude: Anthropic;
  agentmail: AgentMailClient;
  inbox: any;
  model: string;
  userEmail: string;
}): Promise<{ sent: boolean; itemCount: number; reason?: string }> {
  const { claude, agentmail, inbox, model, userEmail } = opts;
  const items = getRecentItems(24);
  if (!items.length) return { sent: false, itemCount: 0, reason: "no items in last 24h" };

  console.log(`  📊 Building digest from ${items.length} item(s)…`);
  const response = await claude.messages.create({
    model,
    max_tokens: 4096,
    system: buildDigestPrompt(),
    tools: [COMPOSE_DIGEST_TOOL, SKIP_DIGEST_TOOL],
    tool_choice: { type: "any" },
    messages: [{ role: "user", content: itemsAsUserMessage(items) }],
  });

  for (const block of response.content) {
    if (block.type !== "tool_use") continue;
    const input = block.input as any;
    if (block.name === "skip_digest") {
      return { sent: false, itemCount: items.length, reason: input.reason || "" };
    }
    if (block.name === "compose_digest") {
      const subject =
        input.subject ||
        `Newsletter digest — ${new Date().toLocaleDateString("en-US", { month: "long", day: "numeric" })}`;
      const body = input.body || "(empty body)";
      console.log(`  📨 Sending digest to ${userEmail} (${body.length} chars)…`);
      await agentmail.inboxes.messages.send(inbox.inboxId, {
        to: [userEmail],
        subject,
        text: body,
      });
      clearRecent(items);
      return { sent: true, itemCount: items.length };
    }
  }
  return {
    sent: false,
    itemCount: items.length,
    reason: "Claude did not call any tool",
  };
}
