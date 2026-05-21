/**
 * Parse the user's one-line reply on a request thread.
 */

const APPROVE = new Set([
  "approve", "approved", "yes", "y", "ship", "ok", "okay", "go", "lgtm",
  "✅", "👍", "send it", "do it", "accept", "confirm",
]);

const DECLINE = new Set([
  "decline", "declined", "deny", "denied", "no", "n", "reject", "rejected",
  "kill", "block", "stop", "❌", "👎", "abort",
]);

const DEFER_RE = /^(defer|snooze|wait|hold|pause|later)\s*(?:by\s*)?(\d+)\s*(d|day|days|w|wk|wks|week|weeks|h|hr|hrs|hour|hours)?/i;
const CHANGES_RE = /^(?:request\s+changes|edit|revise|change|modify|amend)\s*[:\-]?\s*(.*)/is;
const DECLINE_REASON_RE = /^(?:decline|reject|no|deny)\s*[:\-]\s*(.+)/is;

export interface Decision {
  decision: "approve" | "decline" | "defer" | "changes" | "unknown";
  reason?: string;
  days?: number;
  changes_text?: string;
}

export function parse(text: string): Decision {
  if (!text) return { decision: "unknown" };
  const lines = text.trim().split("\n");
  if (!lines.length) return { decision: "unknown" };
  let first = lines[0].trim().toLowerCase().replace(/[.!?\s]+$/, "");

  let m = DECLINE_REASON_RE.exec(first);
  if (m) return { decision: "decline", reason: m[1].trim() };

  m = DEFER_RE.exec(first);
  if (m) {
    const n = parseInt(m[2], 10);
    const unit = (m[3] || "d").toLowerCase();
    let days: number;
    if (unit.startsWith("h")) days = Math.max(1, Math.floor(n / 24));
    else if (unit.startsWith("w")) days = n * 7;
    else days = n;
    return { decision: "defer", days };
  }

  m = CHANGES_RE.exec(first);
  if (m) return { decision: "changes", changes_text: (m[1] || "").trim() };

  if (APPROVE.has(first)) return { decision: "approve" };
  if (DECLINE.has(first)) return { decision: "decline", reason: "" };

  if (first.startsWith("approve ") || first.startsWith("accept ") ||
      first.startsWith("ship ") || first.startsWith("go ahead")) {
    return { decision: "approve" };
  }

  return { decision: "unknown" };
}
