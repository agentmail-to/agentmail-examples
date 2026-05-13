# AgentMail Browser Signup Agent

> Sign up + verify on any site that emails you.

_Part of the [AgentMail templates collection](https://agentmail.to/build/templates) — runnable open-source agents you can clone and ship in minutes._

A browser agent that signs itself up for any service and completes the verification step using its own inbox.

> **Why this exists.** Most of the web is gated behind email verification — signups, OTPs, 2FA, magic links, confirmation flows. A browser agent without its own inbox gets stuck on the verification wall. This template gives the agent an inbox so it can complete the entire flow autonomously: navigate, fill the form, submit, retrieve the verification email, extract the code or link, and finish.

The same shape unlocks **2FA / OTP retrieval**, **booking confirmations**, **ephemeral testing accounts**, and **trial harvesting at scale** — see each language's README for examples.

## Pick your language

The two implementations take different shapes because **Browser Use is Python-only**:

- [**Python**](./python) — uses [Browser Use](https://browser-use.com) for **LLM-driven autonomous browsing**. You give the agent a natural-language task and it figures out how to drive the page. Two AgentMail tools (`get_email_address`, `get_latest_email`) are wired in as agent tools.
- [**TypeScript**](./typescript) — uses [Playwright](https://playwright.dev) for **deterministic browsing**. You configure form selectors + values; the agent's role is the email-verification leg (poll inbox, extract OTP/link via Claude, complete verification). For LLM-driven browsing in TS, see [Stagehand](https://stagehand.dev).

Both versions deliver the same headline value — **the agent's own inbox handles email-gated steps** — but with different ergonomics for browser control.

## What you'll need

- An AgentMail API key — https://console.agentmail.to
- An Anthropic API key — https://console.anthropic.com
- **Python 3.11+** (for the Python version — Browser Use requirement) or Node.js 18+

## Use cases

- **Account creation** — sign up for any service that requires email verification.
- **2FA / OTP flows** — log in to a service that sends a code mid-session; agent retrieves and uses it.
- **Confirmation emails** — book a flight / hotel / restaurant, extract structured details from the confirmation.
- **Trial harvesting** — sign up for N competitor SaaS trials in parallel for research, each with its own ephemeral inbox.
- **Ephemeral test accounts** — spin up clean accounts against your own product without polluting your real inbox.

## Beyond this template

- **Browser Use Cloud** has built-in AgentMail integration: every Cloud session gets an ephemeral inbox automatically with no `AGENTMAIL_API_KEY` needed. The Python version can switch to it by passing `Browser(use_cloud=True)`.
- **CAPTCHA** — neither implementation solves CAPTCHAs. Pause and notify on detection, or hook in a CAPTCHA-solving service.
- **Run in parallel** — both versions can run N tasks concurrently with `asyncio.gather` (Python) or `Promise.all` (TS). Each gets its own inbox.

## License

MIT
