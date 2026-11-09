/**
 * Minimal MailVeri client + send policy.
 *
 * Uses the single-address endpoint documented at https://mailveri.com/docs/:
 *
 *   POST https://api.mailveri.com/v1/verify-mail/
 *   Authorization: Bearer <MAILVERI_API_KEY>
 *   {"email": "jane.doe@example.com"}
 *
 *   -> {"error": 0, "status": "VALID", "email": "...", "balance": 999, "message": "..."}
 *
 * `error` is 0 on success and 2 when the account is out of credits.
 */

const BASE_URL = (process.env.MAILVERI_BASE_URL || "https://api.mailveri.com").replace(/\/+$/, "");

export type Decision = "send" | "skip" | "review";

export class MailVeriError extends Error {
  /** `fatal` means stop the run (auth / credits). */
  constructor(message: string, public fatal = false) {
    super(message);
  }
}

export interface Verification {
  email: string;
  status: string; // VALID, INVALID, DISPOSABLE, ROLE_ACCOUNT, CATCH_ALL, FULL_INBOX, UNKNOWN
  balance: number | null;
  message: string;
}

export async function verify(email: string, apiKey: string): Promise<Verification> {
  let resp: Response;
  try {
    resp = await fetch(`${BASE_URL}/v1/verify-mail/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
      signal: AbortSignal.timeout(30_000),
    });
  } catch (e: any) {
    throw new MailVeriError(`network error: ${e.message}`);
  }

  if (resp.status === 401 || resp.status === 403) {
    throw new MailVeriError("invalid or unauthorized MAILVERI_API_KEY", true);
  }
  if (resp.status === 429) throw new MailVeriError("rate limited (1 request/second for single verify)");

  let data: any;
  try { data = await resp.json(); }
  catch { throw new MailVeriError(`non-JSON response (HTTP ${resp.status})`); }

  const error = data.error ?? 0;
  if (error === 2) throw new MailVeriError(data.message || "not enough credits", true);
  if (error !== 0) throw new MailVeriError(data.message || `verification failed (error=${error})`);

  return {
    email: data.email || data.mail || email,
    status: String(data.status || "UNKNOWN").toUpperCase(),
    balance: data.balance ?? null,
    message: data.message ?? "",
  };
}

/**
 * Map a MailVeri status to send / skip / review.
 *
 * - VALID: send.
 * - INVALID, DISPOSABLE, FULL_INBOX: skip. Sending these only adds bounces.
 * - ROLE_ACCOUNT: shared inboxes (info@, sales@). Deliverable, but cold outreach
 *   to them tends to get ignored or flagged. Review by default.
 * - CATCH_ALL: the domain accepts everything, so the mailbox itself can't be
 *   confirmed. Review by default.
 * - UNKNOWN (or anything new): the mail server didn't give a clear answer.
 *   Review, never send blind.
 */
export function decide(status: string, sendRoleAccounts = false, sendCatchAll = false): Decision {
  switch ((status || "").toUpperCase()) {
    case "VALID": return "send";
    case "INVALID":
    case "DISPOSABLE":
    case "FULL_INBOX": return "skip";
    case "ROLE_ACCOUNT": return sendRoleAccounts ? "send" : "review";
    case "CATCH_ALL": return sendCatchAll ? "send" : "review";
    default: return "review";
  }
}
