# Crosspost Plan: Cold Email Researcher

## Show HN Post

**Title:** Show HN: AI agent that researches prospects and sends cold emails from its own inbox

**Body:**
Built an agent that automates the research-then-email pipeline for B2B outreach.

You give it a CSV of prospects with domains. For each one, it researches the company, finds a relevant angle, writes a personalized email, and sends it from a dedicated inbox via AgentMail (https://agentmail.to).

Then it monitors for replies, classifies them (interested, objection, question), and auto-responds to interested prospects with a calendar link.

The research step is what makes this different from mail-merge tools. Each email references something specific about the prospect's company.

Python, ~200 lines. MIT licensed.

Repo: https://github.com/agentmail-to/cold-email-researcher

---

## Dev.to Article

**Title:** Build a Cold Email Agent That Researches Prospects Before Writing

**Tags:** python, ai, sales, automation

---

Mail merge is dead. Prospects can spot a template from the first line. What works is genuine research followed by a specific, relevant email.

The problem: research takes time. For a 100-prospect campaign, you are looking at hours of reading websites and writing custom emails.

This tutorial builds a Python agent that does the research and writing for you, then sends each email from its own dedicated inbox.

### The architecture

1. Create a dedicated inbox with AgentMail
2. For each prospect: research their company domain with GPT-4o-mini
3. Generate a personalized email using the research
4. Send from the agent's inbox
5. Poll for replies, classify, and respond

### Key code

```python
from agentmail import AgentMail

client = AgentMail(api_key=os.environ["AGENTMAIL_API_KEY"])
inbox = client.inboxes.create(display_name="Sales Outreach")

# Research, generate, send
research = research_prospect("acme.com")
email = generate_email("Sarah", "Acme", research)

client.messages.send(
    inbox_id=inbox.id,
    to=["sarah@acme.com"],
    subject=email["subject"],
    text=email["body"],
    labels=["cold-outreach"],
)
```

### Why a dedicated inbox?

Your personal email has reputation. Mass outreach from it risks deliverability for all your email. A dedicated agent inbox keeps your personal email clean and your agent's activity isolated.

Full code: [github.com/agentmail-to/cold-email-researcher](https://github.com/agentmail-to/cold-email-researcher)

---

## X Thread (6 tweets)

**Tweet 1:**
Built an AI agent that researches prospects and writes cold emails from its own inbox.

Not mail merge. Actual research per prospect.

Open source, ~200 lines of Python.

**Tweet 2:**
How it works: give it a CSV with prospect names and company domains.

For each one, GPT-4o-mini researches the company and finds a specific angle to reference in the email.

**Tweet 3:**
The agent creates its own email address via @AgentMailTo.

Prospects see a real reply-to address. Replies go to the agent, not your inbox.

**Tweet 4:**
When a reply comes in, the agent classifies it:
- Interested -> sends calendar link
- Objection -> flags for human review
- Out of office -> retries later

**Tweet 5:**
Why not just use your Gmail?

Mass outreach from a personal address risks your deliverability. A dedicated agent inbox isolates the risk.

**Tweet 6:**
Repo: github.com/agentmail-to/cold-email-researcher

pip install agentmail openai, add API keys, run.

MIT licensed.
