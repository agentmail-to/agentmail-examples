/**
 * Helper: poll an AgentMail inbox for the next verification email and pull
 * the OTP code or verification link out of it.
 *
 * Pattern: after Playwright submits a signup form, call `waitForVerification`
 * to block until the verification email arrives, then use the returned `otp`
 * or `link` to complete the flow.
 */

import type { AgentMailClient } from "agentmail";
import Anthropic from "@anthropic-ai/sdk";

export interface VerificationResult {
  /** The full message body (text or HTML→text). */
  body: string;
  /** Numeric or short alphanumeric verification code, if one was found. */
  otp: string | null;
  /** Verification link URL, if one was found (preferring buttons / "verify" anchors). */
  link: string | null;
  /** The subject of the verification email. */
  subject: string;
}

/** Strip HTML tags & decode common entities. */
function htmlToText(html: string): string {
  return html
    .replace(/<script\b[^>]*>[\s\S]*?<\/script\s*>/gi, "")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style\s*>/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Wait up to `timeoutSeconds` for a new email in the inbox.
 * Polls every `pollIntervalSeconds`; returns the first unread message.
 */
export async function waitForVerificationEmail(
  agentmail: AgentMailClient,
  inboxId: string,
  opts: {
    timeoutSeconds?: number;
    pollIntervalSeconds?: number;
    /** Optional substring filter on subject — useful if other mail might land. */
    subjectContains?: string;
  } = {},
): Promise<VerificationResult> {
  const timeoutMs = (opts.timeoutSeconds ?? 120) * 1000;
  const intervalMs = (opts.pollIntervalSeconds ?? 5) * 1000;
  const start = Date.now();

  while (Date.now() - start < timeoutMs) {
    const resp = await agentmail.inboxes.messages.list(inboxId, {
      labels: ["unread"],
    });
    const candidates = (resp.messages || []).filter((m: any) => {
      if (!opts.subjectContains) return true;
      return (m.subject || "")
        .toLowerCase()
        .includes(opts.subjectContains.toLowerCase());
    });

    if (candidates.length) {
      // Fetch the freshest one (sorted by timestamp desc)
      candidates.sort((a: any, b: any) => {
        const ta = new Date(a.timestamp).getTime();
        const tb = new Date(b.timestamp).getTime();
        return tb - ta;
      });
      const stub = candidates[0];

      // Get full message body
      const full = await agentmail.inboxes.messages.get(
        inboxId,
        stub.messageId,
      );

      // Mark read so we don't re-process
      await agentmail.inboxes.messages.update(inboxId, full.messageId, {
        removeLabels: ["unread"],
      });

      const body =
        (full.text && full.text.trim()) ||
        (full.html ? htmlToText(full.html) : "") ||
        "";

      return {
        body,
        otp: extractOtp(body),
        link: extractLink(body),
        subject: full.subject || "",
      };
    }

    await new Promise((r) => setTimeout(r, intervalMs));
  }

  throw new Error(
    `No verification email arrived in ${opts.timeoutSeconds ?? 120}s`,
  );
}

/**
 * Extract a numeric/alphanumeric OTP from the email body.
 *
 * Strategy: find a keyword like "code" / "otp" / "verification" / "pin",
 * then look within the next ~80 chars for an OTP-shaped token. We require
 * the token to either be all digits OR contain at least one digit when
 * mixed with uppercase letters — that excludes English words like "code"
 * or "your" that would otherwise match `[A-Z0-9]{4,10}` under `/i`.
 */
export function extractOtp(body: string): string | null {
  const lower = body.toLowerCase();
  const keywords = [
    "verification code",
    "code is",
    "your code",
    "code:",
    "code ",  // catches "Use code 8344"
    "otp",
    "verification",
    "verify",
    "pin",
    "token",
  ];

  for (const kw of keywords) {
    const idx = lower.indexOf(kw);
    if (idx < 0) continue;
    const slice = body.slice(idx, idx + 80);

    // Pure digits, 4-8 chars
    const digitMatch = slice.match(/\b(\d{4,8})\b/);
    if (digitMatch) return digitMatch[1];

    // Mixed upper+digit, 4-10 chars (lookahead enforces "must contain a digit")
    const alphaNumMatch = slice.match(/\b((?=[A-Z0-9]*\d)[A-Z0-9]{4,10})\b/);
    if (alphaNumMatch) return alphaNumMatch[1];
  }

  // Fallback: any standalone 6-digit code anywhere in the body
  const fallback = body.match(/\b(\d{6})\b/);
  return fallback ? fallback[1] : null;
}

/**
 * Extract a verification link from the email body.
 * Prefers links whose text or URL contains "verify" / "confirm" / "activate".
 */
export function extractLink(body: string): string | null {
  // Pull all URLs
  const urls = body.match(/https?:\/\/[^\s)<>"]+/g) || [];
  if (!urls.length) return null;

  // Prefer "verify" / "confirm" / "activate" hints in the URL
  const verifyish = urls.find((u) =>
    /(verify|confirm|activate|magic|signin|auth)/i.test(u),
  );
  return verifyish || urls[0];
}

/**
 * For tricky emails where the OTP/link isn't obvious, use Claude to extract
 * structured fields. This is a fallback for messy verification emails.
 */
export async function extractWithClaude(
  body: string,
  opts: { anthropicApiKey: string; model?: string } = { anthropicApiKey: "" },
): Promise<{ otp: string | null; link: string | null }> {
  const claude = new Anthropic({ apiKey: opts.anthropicApiKey });
  const response = await claude.messages.create({
    model: opts.model ?? "claude-sonnet-4-6",
    max_tokens: 256,
    messages: [
      {
        role: "user",
        content: `Extract the verification OTP code and verification link from this email body. Respond with ONLY a JSON object: {"otp": "...", "link": "..."}. Use null for any value you can't find.\n\n---\n${body}\n---`,
      },
    ],
  });
  const text = response.content[0].type === "text" ? response.content[0].text : "";
  const match = text.match(/\{[\s\S]*\}/);
  if (!match) return { otp: null, link: null };
  try {
    const parsed = JSON.parse(match[0]);
    return {
      otp: parsed.otp ?? null,
      link: parsed.link ?? null,
    };
  } catch {
    return { otp: null, link: null };
  }
}
