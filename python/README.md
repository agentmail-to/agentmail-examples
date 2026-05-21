# Browser Signup Agent — Python

A browser agent that **signs up + verifies on any site that emails you**. Built on [AgentMail](https://agentmail.to) + [Browser Use](https://browser-use.com) + Claude.

> **Why this exists.** Most of the web is gated behind email verification — signups, OTPs, 2FA, magic links, confirmation flows. A browser agent without its own inbox gets stuck on the verification step. AgentMail gives the agent an inbox; it completes the entire flow.

## Setup (5 minutes)

> **Requires Python 3.11+** (Browser Use requirement, not 3.10).

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   # First-time only — install Chromium:
   uvx browser-use install
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in:
   - `AGENTMAIL_API_KEY` — from https://console.agentmail.to
   - `ANTHROPIC_API_KEY` — from https://console.anthropic.com
   - `TASK` — the natural-language task. The default signs up for Hacker News; replace with any other URL/instructions.

3. **Run**
   ```bash
   python agent.py
   ```
   The agent creates a fresh AgentMail inbox, opens a browser (headed by default — set `HEADLESS=true` in `.env` for CI), and drives the signup end-to-end.

## How it works

The agent has two AgentMail-backed tools registered through `EmailTools`:

| Tool | What it does |
| --- | --- |
| `get_email_address()` | Returns the inbox address to fill into "Email" fields on signup forms. |
| `get_latest_email(max_age_minutes=5)` | Polls for an unread email; if none exists, opens a websocket to the inbox and waits up to `EMAIL_TIMEOUT_SECONDS` for one to arrive. Returns subject + body so the agent can extract OTP codes or click verification links. |

The flow:

1. `agent.py` creates a fresh AgentMail inbox via `AsyncAgentMail.inboxes.create()`.
2. `EmailTools(email_client, inbox=inbox)` registers the two tools above on a Browser Use `Tools` subclass.
3. `Agent(task=..., tools=email_tools, llm=ChatAnthropic(...), browser=Browser())` runs the LLM-driven browser loop. Claude decides when to call `get_email_address` (during form fill) and `get_latest_email` (after submit).
4. The agent returns a summary of what it did — typically the credentials it created and the verification status.

## Files

| File | What it does |
| --- | --- |
| `agent.py` | Main entrypoint. Creates the inbox, wires up `EmailTools`, runs Browser Use's `Agent`. |
| `email_tools.py` | The `EmailTools` class — mirrors `browser-use/examples/integrations/agentmail/email_tools.py`. Self-contained so this template doesn't depend on the upstream example folder. |
| `.env.example` | Copy to `.env` and fill in. The `TASK` value drives what the agent does. |

## Use cases beyond signup

The same pattern unlocks any email-gated browser flow:

- **2FA / OTP retrieval** — log in to a service, the agent fetches the texted-or-emailed OTP, completes login.
- **Booking confirmations** — book a flight / hotel / restaurant, extract reservation details from the confirmation email.
- **Trial harvesting** — sign up for N competitor SaaS trials in parallel for research, each with its own ephemeral inbox.
- **Newsletter intelligence** — subscribe to N newsletters and aggregate the content downstream.

Just change the `TASK` string.

## Beyond this template

- **Browser Use Cloud** has built-in AgentMail integration: every Cloud session gets an ephemeral inbox automatically with no `AGENTMAIL_API_KEY` needed. To switch, replace `Browser(headless=...)` with `Browser(use_cloud=True)` and provide `BROWSER_USE_API_KEY`. Trades free for fully-managed.
- **CAPTCHA handling** — the agent doesn't currently solve CAPTCHAs. Pause and notify on detection (the system prompt mentions this), or hook in a CAPTCHA-solving service (2Captcha, anti-captcha) as another tool.
- **Persist credentials** — after the agent finishes, save the credentials it generated to a vault (1Password CLI, Bitwarden, Doppler).
- **Run in parallel** — kick off N tasks at once with `asyncio.gather([main() for _ in range(N)])` for trial harvesting at scale. Each gets its own inbox.
