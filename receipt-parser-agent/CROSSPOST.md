# Crosspost Plan: Receipt Parser Agent

## Show HN Post

**Title:** Show HN: Forward receipts to an AI agent, get a weekly expense report

**Body:**
Built an agent with its own email address that parses receipt emails. Forward your receipts as they come in, and it sends you a categorized expense report every Friday.

It extracts vendor, line items, tax, and total with GPT-4o-mini. Categorizes each expense (travel, meals, software, supplies). Confirms each receipt back to you with a running total.

No apps, no photos. Just forward the email.

Uses AgentMail (https://agentmail.to) for the inbox. Python, ~200 lines.

Repo: https://github.com/agentmail-to/receipt-parser-agent

---

## Dev.to Article

**Title:** Build a Receipt-Parsing AI Agent That Sends Weekly Expense Reports

**Tags:** python, ai, fintech, automation

---

Expense tracking should not require opening an app. This tutorial builds an agent that parses receipts from forwarded emails and compiles a weekly expense report.

### How it works

1. Create an expense inbox with AgentMail
2. Forward receipts to the inbox
3. GPT-4o-mini extracts vendor, items, total, and category
4. Agent confirms each receipt back to you
5. Weekly summary sent every Friday

Full code: [github.com/agentmail-to/receipt-parser-agent](https://github.com/agentmail-to/receipt-parser-agent)

---

## X Thread (5 tweets)

**Tweet 1:**
Built an AI agent that parses receipt emails and sends weekly expense reports.

Forward receipts to it. That is the entire workflow.

**Tweet 2:**
The agent extracts vendor, line items, tax, total, and category from every receipt email. Confirms back to you with a running total.

**Tweet 3:**
Every Friday, it sends a categorized expense report to your email. Travel, meals, software, supplies. With totals per category.

**Tweet 4:**
No apps. No photos. Forward the receipt email and forget about it. The agent built on @AgentMailTo handles the rest.

**Tweet 5:**
Repo: github.com/agentmail-to/receipt-parser-agent

Python, MIT. ~200 lines.
