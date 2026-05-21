/**
 * Parse the user's reply on a needs_review payment thread.
 */

const APPROVE = new Set([
  "approve", "approved", "yes", "y", "pay", "ship", "ok", "okay", "go", "lgtm",
  "✅", "👍", "send it", "do it", "confirm", "authorize", "authorise",
]);

const DECLINE = new Set([
  "decline", "declined", "deny", "denied", "no", "n", "reject", "rejected",
  "kill", "block", "stop", "❌", "👎", "abort", "skip",
]);

const DECLINE_REASON_RE = /^(?:decline|reject|no|deny|skip)\s*[:\-]\s*(.+)/is;

export interface Decision {
  decision: "approve" | "decline" | "unknown";
  reason?: string;
}

export function parse(text: string): Decision {
  if (!text) return { decision: "unknown" };
  const lines = text.trim().split("\n");
  if (!lines.length) return { decision: "unknown" };
  let first = lines[0].trim().toLowerCase().replace(/[.!?\s]+$/, "");

  const m = DECLINE_REASON_RE.exec(first);
  if (m) return { decision: "decline", reason: m[1].trim() };

  if (APPROVE.has(first)) return { decision: "approve" };
  if (DECLINE.has(first)) return { decision: "decline", reason: "" };
  if (first.startsWith("approve ") || first.startsWith("pay ") ||
      first.startsWith("authorize ") || first.startsWith("authorise ")) {
    return { decision: "approve" };
  }
  return { decision: "unknown" };
}
