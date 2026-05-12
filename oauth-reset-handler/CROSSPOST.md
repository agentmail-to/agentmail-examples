# Crosspost Plan: OAuth Reset Handler

## Show HN Post

**Title:** Show HN: Handle email-based OTP and password resets programmatically with AgentMail

**Body:**
When AI agents interact with web services, they hit email-based verification walls: OTPs, magic links, password reset codes. This utility creates a temporary inbox, waits for the verification email, and extracts the code or link.

Uses AgentMail (https://agentmail.to) to create disposable inboxes on the fly and GPT-4o-mini to extract codes from varied email formats.

Use case: agent automation pipelines where you need to get past email verification without human intervention.

Python, ~100 lines.

Repo: https://github.com/agentmail-to/oauth-reset-handler

---

## Dev.to Article

**Title:** Programmatic Email Verification for AI Agents: OTPs, Magic Links, and Reset Codes

**Tags:** python, ai, authentication, automation

---

Email verification is a wall for automated agents. Your agent needs to sign up for a service, but the service sends a verification code to an email address. Your agent needs to reset a password, but the reset link arrives via email.

This tutorial builds a utility that creates temporary inboxes on-the-fly, waits for verification emails, and extracts codes programmatically.

### The pattern

```python
from src.main import get_verification_code

result = get_verification_code(
    service_name="example.com",
    from_domain="example.com",
)
print(result["value"])  # "482913" or "https://example.com/verify?token=..."
```

Full code: [github.com/agentmail-to/oauth-reset-handler](https://github.com/agentmail-to/oauth-reset-handler)

---

## X Thread (5 tweets)

**Tweet 1:**
Built a utility for AI agents to handle email-based verification: OTPs, magic links, password reset codes.

Create a temp inbox, wait for the email, extract the code. ~100 lines.

**Tweet 2:**
The pattern: create a disposable inbox via @AgentMailTo, trigger the verification flow, poll for the email, extract the code with GPT-4o-mini.

**Tweet 3:**
Works with any service that sends verification emails. OTPs, magic links, reset codes, confirmation links. The extraction adapts to the email format.

**Tweet 4:**
Temp inboxes are cleaned up after use. No leftover state.

**Tweet 5:**
Repo: github.com/agentmail-to/oauth-reset-handler

Python, MIT. Use as a library in your agent pipeline.
