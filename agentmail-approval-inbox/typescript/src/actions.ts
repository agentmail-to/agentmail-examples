/**
 * Side-effect actions: forward_to / webhook / reply_to_sender.
 */

import { TypeConfig, ActionBlock } from "./typesConfig.js";
import { RequestRow } from "./requestsStore.js";

function interpolate(template: string, fields: Record<string, any>): string {
  return template.replace(/\{(\w+)\}/g, (_, key) => {
    const v = fields[key];
    return (v ?? "") === "" ? "(unspecified)" : String(v);
  });
}

async function postWebhook(url: string, payload: Record<string, any>): Promise<boolean> {
  try {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return true;
  } catch (e: any) {
    console.warn(`  ! webhook failed: ${e.message}`);
    return false;
  }
}

export async function fire(opts: {
  agentmail: any;
  inbox: any;
  requestRow: RequestRow;
  typeConfig: TypeConfig;
  decision: "approve" | "decline";
  decisionArgs?: { reason?: string; changes_text?: string };
}): Promise<string[]> {
  const block: ActionBlock = opts.decision === "approve" ? opts.typeConfig.approve : opts.typeConfig.decline;
  let fields: Record<string, any> = {};
  try { fields = JSON.parse(opts.requestRow.fields_json || "{}"); } catch {}
  const confirmations: string[] = [];

  // 1. forward_to
  if (block.forward_to) {
    try {
      await opts.agentmail.inboxes.messages.forward(opts.inbox.inboxId, opts.requestRow.source_message_id, {
        to: [block.forward_to],
        text:
          `[Approval inbox - ${opts.decision.toUpperCase()}]\n\n` +
          `Type: ${opts.requestRow.type}\n` +
          `Summary: ${opts.requestRow.summary}\n` +
          `Decided by: ${opts.decision}\n\n` +
          `Fields: ${JSON.stringify(fields, null, 2)}\n\n` +
          `Original email forwarded below.`,
      });
      confirmations.push(`forwarded to ${block.forward_to}`);
    } catch (e: any) {
      console.warn(`  ! forward failed: ${e.message}`);
      confirmations.push(`forward to ${block.forward_to} FAILED (${e.message})`);
    }
  }

  // 2. webhook
  if (block.webhook) {
    const ok = await postWebhook(block.webhook, {
      request_id: opts.requestRow.id,
      type: opts.requestRow.type,
      decision: opts.decision,
      summary: opts.requestRow.summary,
      fields,
      source_sender: opts.requestRow.source_sender,
      decided_text: opts.decisionArgs?.reason ?? opts.decisionArgs?.changes_text ?? "",
    });
    confirmations.push(`webhook ${ok ? "fired" : "FAILED"}`);
  }

  // 3. reply_to_sender
  if (block.reply_to_sender) {
    const sender = opts.requestRow.source_sender;
    if (!sender) {
      confirmations.push("reply_to_sender skipped (no source sender on record)");
    } else {
      try {
        const merged = {
          ...fields,
          decision: opts.decision,
          reason: opts.decisionArgs?.reason ?? "",
          changes_text: opts.decisionArgs?.changes_text ?? "",
        };
        const body = interpolate(block.reply_to_sender, merged);
        await opts.agentmail.inboxes.messages.reply(opts.inbox.inboxId, opts.requestRow.source_message_id, {
          text: body,
        });
        confirmations.push(`replied to ${sender}`);
      } catch (e: any) {
        console.warn(`  ! reply_to_sender failed: ${e.message}`);
        confirmations.push(`reply to ${sender} FAILED (${e.message})`);
      }
    }
  }

  if (!confirmations.length) {
    confirmations.push("(no side-effect actions configured for this decision)");
  }
  return confirmations;
}
