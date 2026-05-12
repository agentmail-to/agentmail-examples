# Crosspost Plan: Email to CLI

## Show HN Post

**Title:** Show HN: Run shell commands on a remote machine by sending an email

**Body:**
A bridge between email and your terminal. Send an email with a command in the subject line, get the output back as a reply.

Security: allowlisted commands only, sender verification, no shell expansion, configurable timeout. This is not a backdoor; it is a controlled remote exec interface with an email audit trail.

Uses AgentMail (https://agentmail.to) for the inbox. Python, ~120 lines.

Use cases: IoT devices, air-gapped systems, remote monitoring when SSH is not available.

Repo: https://github.com/agentmail-to/email-to-cli

---

## Dev.to Article

**Title:** Build an Email-to-CLI Bridge: Run Remote Commands via Email

**Tags:** python, devops, iot, automation

---

SSH is great until it is not available. Firewalls, NAT, IoT devices with no SSH daemon. Email goes everywhere.

This tutorial builds a bridge that lets you run commands on a remote machine by emailing an agent. Command goes in the subject line, output comes back as a reply.

Full code: [github.com/agentmail-to/email-to-cli](https://github.com/agentmail-to/email-to-cli)

---

## X Thread (5 tweets)

**Tweet 1:**
Built an email-to-CLI bridge. Send a command in the email subject, get stdout back as a reply.

For when SSH is not available. ~120 lines of Python.

**Tweet 2:**
Security: allowlisted commands, sender verification, no shell expansion, 30s timeout. Not a backdoor. A controlled interface with an email audit trail.

**Tweet 3:**
The agent creates its own inbox via @AgentMailTo. Poll-based, so it works behind NAT and firewalls.

**Tweet 4:**
Use cases: IoT monitoring, air-gapped systems, remote server health checks, teaching tools.

**Tweet 5:**
Repo: github.com/agentmail-to/email-to-cli

Python, MIT licensed.
