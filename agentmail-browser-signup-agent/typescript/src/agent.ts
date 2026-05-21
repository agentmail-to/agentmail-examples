/**
 * AgentMail Browser Signup Agent — TypeScript / Playwright variant.
 *
 * The Python version uses Browser Use's LLM-driven autonomy. Browser Use
 * doesn't ship a TypeScript SDK, so the TS template takes a different shape:
 *
 *   - Playwright drives the browser deterministically.
 *   - You configure the signup form selectors + values in `signupConfig`.
 *   - AgentMail provides the inbox; `waitForVerificationEmail()` polls it.
 *   - Claude extracts the OTP / verification link from the email body.
 *   - Playwright completes the verification step.
 *
 * This is the "show me the email-verification leg" version. For full LLM-
 * driven browsing in TS, see https://stagehand.dev (alternative).
 */

import "dotenv/config";
import { chromium } from "playwright";
import { AgentMailClient } from "agentmail";
import {
  waitForVerificationEmail,
  extractWithClaude,
} from "./waitForEmail.js";

// --- config ------------------------------------------------------------------

const {
  AGENTMAIL_API_KEY,
  ANTHROPIC_API_KEY,
  ANTHROPIC_MODEL = "claude-sonnet-4-6",
  HEADLESS = "false",
} = process.env;

if (!AGENTMAIL_API_KEY) throw new Error("AGENTMAIL_API_KEY required");
if (!ANTHROPIC_API_KEY) throw new Error("ANTHROPIC_API_KEY required");

// --- Signup config -----------------------------------------------------------
//
// Replace this with the form layout for the site you want to sign up to.
// The {{INBOX_EMAIL}} placeholder gets substituted with the AgentMail inbox at
// runtime — that's the whole point of the integration.
//
// The two required Playwright selectors per field can be either CSS or
// Playwright's role/text/label syntax.

interface SignupConfig {
  /** Display name of the target service. Used in logs only. */
  name: string;
  /** URL of the signup page. */
  signupUrl: string;
  /** Form fields keyed by Playwright selector → value. */
  fields: Record<string, string>;
  /** Playwright selector for the submit button on the signup form. */
  submitSelector: string;
  /**
   * What to do with the verification email:
   *   - "click_link"  → click the verification URL extracted from the email.
   *   - "enter_otp"   → fill the OTP into a Playwright selector on the post-submit page.
   */
  verification:
    | { kind: "click_link" }
    | { kind: "enter_otp"; otpSelector: string; otpSubmitSelector?: string };
  /** Optional substring filter for verification email subject. */
  emailSubjectContains?: string;
  /** How long to wait for the verification email (default 120s). */
  emailTimeoutSeconds?: number;
}

const SIGNUP_CONFIG: SignupConfig = {
  name: "Hacker News",
  signupUrl: "https://news.ycombinator.com/login",
  fields: {
    'input[name="acct"]:nth-of-type(2)': "agentmail-demo",
    'input[name="pw"]:nth-of-type(2)': "demo-password-1234",
    // HN doesn't actually use email — this is just a structural example.
    // Replace with a real signup form's selectors when you adapt this.
  },
  submitSelector: 'input[type="submit"][value="create account"]',
  verification: { kind: "click_link" },
  emailSubjectContains: "verify",
  emailTimeoutSeconds: 120,
};

// --- main --------------------------------------------------------------------

async function main(): Promise<void> {
  console.log(`📋 Target: ${SIGNUP_CONFIG.name} (${SIGNUP_CONFIG.signupUrl})\n`);

  // 1. Create a fresh AgentMail inbox
  const agentmail = new AgentMailClient({ apiKey: AGENTMAIL_API_KEY! });
  const inbox = await agentmail.inboxes.create({});
  console.log(`📬 Agent inbox: ${inbox.email}\n`);

  // 2. Spin up a browser and navigate
  const browser = await chromium.launch({
    headless: HEADLESS.toLowerCase() === "true",
  });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log(`🌐 Opening ${SIGNUP_CONFIG.signupUrl}…`);
    await page.goto(SIGNUP_CONFIG.signupUrl, { waitUntil: "domcontentloaded" });

    // 3. Fill the signup form. The {{INBOX_EMAIL}} placeholder is substituted
    //    so the inbox address lands in any "Email" field.
    for (const [selector, rawValue] of Object.entries(SIGNUP_CONFIG.fields)) {
      const value = rawValue.replace(/\{\{INBOX_EMAIL\}\}/g, inbox.email);
      console.log(`✏️  Fill ${selector} → ${value}`);
      await page.fill(selector, value);
    }

    // 4. Submit
    console.log(`📨 Submitting form (${SIGNUP_CONFIG.submitSelector})…`);
    await page.click(SIGNUP_CONFIG.submitSelector);

    // 5. Wait for the verification email
    console.log(`⏳ Waiting for verification email…`);
    let result;
    try {
      result = await waitForVerificationEmail(agentmail, inbox.inboxId, {
        timeoutSeconds: SIGNUP_CONFIG.emailTimeoutSeconds ?? 120,
        subjectContains: SIGNUP_CONFIG.emailSubjectContains,
      });
    } catch (e: any) {
      console.error(`❌ ${e.message}`);
      return;
    }
    console.log(`📧 Got email — subject: "${result.subject}"`);

    // If the regex extractors missed, fall back to Claude.
    let { otp, link } = result;
    if (!otp && !link) {
      console.log(`🔎 No OTP/link found via regex — falling back to Claude…`);
      const claudeExtract = await extractWithClaude(result.body, {
        anthropicApiKey: ANTHROPIC_API_KEY!,
        model: ANTHROPIC_MODEL,
      });
      otp = claudeExtract.otp;
      link = claudeExtract.link;
    }
    console.log(`   OTP: ${otp ?? "(none)"} | Link: ${link ?? "(none)"}`);

    // 6. Complete verification
    if (SIGNUP_CONFIG.verification.kind === "click_link") {
      if (!link) throw new Error("Expected verification link, none found");
      console.log(`🔗 Navigating to ${link}…`);
      await page.goto(link, { waitUntil: "domcontentloaded" });
    } else {
      if (!otp) throw new Error("Expected OTP, none found");
      const v = SIGNUP_CONFIG.verification;
      console.log(`🔢 Filling OTP into ${v.otpSelector}…`);
      await page.fill(v.otpSelector, otp);
      if (v.otpSubmitSelector) {
        await page.click(v.otpSubmitSelector);
      }
    }

    console.log(`\n✅ Signup + verification complete.`);
    console.log(`   Inbox: ${inbox.email}`);
    console.log(`   Final URL: ${page.url()}`);
  } finally {
    await browser.close();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
