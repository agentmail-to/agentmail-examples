# Crosspost Plan: Collections Agent

## Show HN Post

**Title:** Show HN: AI collections agent that sends payment reminders and handles responses

**Body:**
Built an agent that manages payment collection via email. Feed it a CSV of overdue invoices and it handles the rest.

The agent creates its own inbox via AgentMail, sends progressively firmer reminders on a schedule (friendly > firm > urgent > final notice), classifies responses (paid, dispute, payment plan), and escalates disputes to a human.

No call center needed for routine collections. The agent handles the volume, humans handle the edge cases.

Python, ~250 lines.

Repo: https://github.com/agentmail-to/collections-agent

---

## Dev.to Article

**Title:** Build an AI Collections Agent That Manages Payment Follow-ups via Email

**Tags:** python, ai, fintech, automation

---

Payment collection is one of the most repetitive business processes. The sequence is always the same: friendly reminder, firm follow-up, urgent notice, final warning. Most teams either do this manually or use inflexible SaaS tools.

This tutorial builds a Python agent that handles the entire collections pipeline through email.

### The escalation schedule

```python
REMINDER_SCHEDULE = [
    {"days_overdue": 1, "tone": "friendly"},
    {"days_overdue": 7, "tone": "firm"},
    {"days_overdue": 14, "tone": "urgent"},
    {"days_overdue": 30, "tone": "final-notice"},
]
```

The agent generates contextual emails at each stage using GPT-4o-mini. Each email includes the invoice number, amount, and due date.

### Handling replies

When a customer replies "paid," the agent confirms and stops sending reminders. Disputes and payment plan requests get escalated to a human.

Full code: [github.com/agentmail-to/collections-agent](https://github.com/agentmail-to/collections-agent)

---

## X Thread (5 tweets)

**Tweet 1:**
Built an AI collections agent that sends payment reminders and handles responses via email.

Friendly -> firm -> urgent -> final notice. All automated.

**Tweet 2:**
Feed it a CSV of overdue invoices. It creates its own inbox via @AgentMailTo and sends reminders on a schedule.

Each reminder is contextual: includes the invoice number, amount, and days overdue.

**Tweet 3:**
When customers reply, the agent classifies: paid, dispute, payment plan. Paid = stop reminders. Dispute = escalate to human.

**Tweet 4:**
Why email? Because collections follow-up is inherently email-based. This agent fits the existing workflow without requiring portals or new tools.

**Tweet 5:**
Repo: github.com/agentmail-to/collections-agent

Python, MIT licensed. ~250 lines.
