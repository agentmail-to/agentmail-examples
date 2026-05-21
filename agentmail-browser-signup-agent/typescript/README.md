# Browser Signup Agent — TypeScript

Playwright drives the browser. AgentMail receives the verification email. Claude extracts the OTP or verification link. Playwright completes the verification step.

> **Why this shape (vs Python).** The Python version of this template uses [Browser Use](https://browser-use.com), which is LLM-autonomous — you give it a task in natural language and it figures out how to drive the page. Browser Use doesn't ship a TypeScript SDK, so this version uses **Playwright + a configured form layout** instead. Less autonomous, more deterministic. The headline value — **the agent's own inbox handling email-gated verification steps** — is identical.
>
> For LLM-driven browsing in TypeScript, see [Stagehand](https://stagehand.dev). You can drop the `waitForVerificationEmail` helper from this template into a Stagehand flow without changes.

## Setup (3 minutes)

1. **Install dependencies + browser**
   ```bash
   npm install
   npx playwright install chromium
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in `AGENTMAIL_API_KEY` and `ANTHROPIC_API_KEY`.

3. **Edit `SIGNUP_CONFIG` in `src/agent.ts`**
   The example config targets a generic signup form. Replace the `signupUrl`, `fields`, `submitSelector`, and `verification` block with the actual selectors for the site you want to sign up to. Use the `{{INBOX_EMAIL}}` placeholder in any field value — the agent substitutes it with the real inbox address at runtime.

4. **Run**
   ```bash
   npm start
   ```

## How it works

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│  Playwright  │       │   Signup     │       │  AgentMail   │       │   Claude     │
│  (form fill) │ ─────▶│   page       │ ─────▶│   inbox      │ ─────▶│  (extract    │
└──────────────┘       │   submits    │       │   receives   │       │   OTP/link)  │
                       └──────────────┘       │   verify mail│       └──────┬───────┘
                                              └──────────────┘              │
                                                                            ▼
                                                                  ┌──────────────────┐
                                                                  │  Playwright      │
                                                                  │  clicks link OR  │
                                                                  │  fills OTP       │
                                                                  └──────────────────┘
```

The flow:

1. `agent.ts` creates a fresh AgentMail inbox via `client.inboxes.create()`.
2. Playwright navigates to `signupUrl`, fills each field per `SIGNUP_CONFIG.fields` (substituting `{{INBOX_EMAIL}}` → the real inbox address), and clicks `submitSelector`.
3. `waitForVerificationEmail()` polls the AgentMail inbox until a message arrives (or times out).
4. The regex extractors `extractOtp` / `extractLink` try first. If they miss, we fall back to **`extractWithClaude`** which prompts Claude to return `{otp, link}` as JSON. Resilient to weirdly-formatted verification emails.
5. Per the `SIGNUP_CONFIG.verification` block, Playwright either navigates to the verification link or fills the OTP into a configured selector.

## Files

| File | What it does |
| --- | --- |
| `src/agent.ts` | Main entrypoint. Configure `SIGNUP_CONFIG` here. |
| `src/waitForEmail.ts` | The reusable email-verification helper. Drop it into any other Playwright (or Stagehand, or Puppeteer) project. |
| `.env.example` | Copy to `.env`. Just two API keys. |

## Use cases beyond signup

The same pattern works for:

- **2FA / OTP retrieval** — log in via Playwright, OTP lands in the AgentMail inbox, the helper extracts it, Playwright fills the second-factor input.
- **Confirmation extraction** — book a flight / hotel / restaurant, the confirmation email lands in AgentMail, extract structured data with Claude.
- **Ephemeral testing accounts** — spin up N test accounts in parallel against your own product, each with a clean inbox.

## Beyond this template

- **LLM-driven form filling** — replace the deterministic `SIGNUP_CONFIG` with [Stagehand](https://stagehand.dev) calls (`page.act("fill in the signup form")`) for full agent autonomy in TS.
- **CAPTCHA handling** — none here. Pause and notify on detection, or hook in a CAPTCHA-solving service as another step.
- **Persist credentials** — after the agent finishes, save the credentials to a vault (1Password CLI, Bitwarden, Doppler).
- **Run in parallel** — `Promise.all([...])` on N targets at once. Each gets its own ephemeral inbox.
