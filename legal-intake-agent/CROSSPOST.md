# Crosspost Plan: Legal Intake Agent

## Show HN Post

**Title:** Show HN: AI legal intake agent that qualifies leads via email 24/7

**Body:**
Built an agent that handles legal intake through its own email address. Potential clients email the agent, it sends a structured questionnaire, classifies the case type with GPT-4o-mini, and routes qualified leads to the right attorney.

The problem it solves: law firms lose leads because intake is slow. Someone emails at 11pm about a car accident, and nobody responds until Monday. This agent responds in seconds, collects the right information, and routes the case.

It uses AgentMail (https://agentmail.to) for the inbox infrastructure, so the agent has a dedicated address and thread history separate from the firm's main email.

Python, ~200 lines. Routing is configured via a JSON file mapping case types to attorney emails.

Repo: https://github.com/agentmail-to/legal-intake-agent

---

## Dev.to Article

**Title:** Build a 24/7 Legal Intake Agent That Qualifies Leads via Email

**Tags:** python, ai, legal, automation

---

Law firms have a lead problem. Not volume, but speed. A potential client emails about an injury case at 11pm. By Monday, they have called three other firms.

This tutorial builds an AI agent that handles intake immediately, around the clock, through its own email inbox.

### What the agent does

1. Receives inquiry from potential client
2. Sends structured intake questionnaire
3. Extracts and classifies case details
4. Routes qualified leads to the right attorney
5. Politely declines cases outside the firm's practice areas

### Routing logic

```json
{
  "personal-injury": {"name": "Jane Smith", "email": "jsmith@firm.com"},
  "employment": {"name": "Bob Johnson", "email": "bjohnson@firm.com"}
}
```

Full code: [github.com/agentmail-to/legal-intake-agent](https://github.com/agentmail-to/legal-intake-agent)

---

## X Thread (5 tweets)

**Tweet 1:**
Built an AI legal intake agent that qualifies leads via email, 24/7.

Responds in seconds. Collects case details. Routes to the right attorney. ~200 lines of Python.

**Tweet 2:**
Someone emails about a car accident at 11pm. The agent responds immediately with an intake questionnaire.

No more lost leads because the office was closed.

**Tweet 3:**
GPT-4o-mini classifies the case (personal injury, employment, contract, etc.) and checks for statute of limitations concerns.

Qualified leads get routed to the right attorney.

**Tweet 4:**
The agent runs on its own inbox via @AgentMailTo. Separate from the firm's main email. Full thread history and label tracking.

**Tweet 5:**
Repo: github.com/agentmail-to/legal-intake-agent

Python, MIT licensed. Configure attorneys.json and run.
