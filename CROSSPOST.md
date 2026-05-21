# Crosspost Plan: Recruiter Coordinator

## Show HN Post

**Title:** Show HN: Open-source AI recruiting agent with its own email inbox

**Body:**
Hey HN, I built an AI agent that handles recruiting outreach end-to-end through its own email address.

The agent creates an inbox via AgentMail (https://agentmail.to), sends personalized outreach from a CSV of candidates, monitors for replies, classifies responses with GPT-4o-mini, and sends follow-ups on a schedule.

The key insight: giving the agent its own email address (not yours) means it can operate autonomously without touching your personal inbox, and candidates see a real email address they can reply to.

Stack: Python, AgentMail SDK, OpenAI. About 150 lines of code.

Repo: https://github.com/agentmail-to/recruiter-coordinator

Would love feedback on the classification prompt and the follow-up logic.

---

## Dev.to Article

**Title:** Build an AI Recruiting Agent That Manages Its Own Email Inbox

**Tags:** python, ai, recruiting, automation

---

Recruiting coordinators spend hours on repetitive email tasks: sending outreach, tracking replies, following up with non-responders. What if an AI agent could handle the volume work?

In this tutorial, you will build a Python agent that:

1. Gets its own email address via AgentMail
2. Sends personalized outreach to candidates from a CSV
3. Monitors its inbox for replies
4. Classifies responses using GPT-4o-mini
5. Sends follow-ups on a configurable schedule

### Why give the agent its own inbox?

Most email automation tools send from your personal address. That creates problems:

- Your inbox fills with automated replies
- Candidates reply to you, not the agent
- You cannot run multiple agents without address conflicts

AgentMail solves this by letting you create dedicated inboxes programmatically. Each agent gets its own address, its own threads, its own labels.

### Setup

```bash
pip install agentmail openai
```

Set your API keys:

```bash
export AGENTMAIL_API_KEY=your_key
export OPENAI_API_KEY=your_key
```

### Step 1: Create the inbox

```python
from agentmail import AgentMail

client = AgentMail(api_key=os.environ["AGENTMAIL_API_KEY"])
inbox = client.inboxes.create(display_name="Recruiter Bot")
print(f"Agent email: {inbox.email}")
```

### Step 2: Send outreach

```python
client.messages.send(
    inbox_id=inbox.id,
    to=["candidate@example.com"],
    subject="Senior Engineer opportunity at Acme",
    text="Hi Jane, I came across your profile...",
    labels=["outreach"],
)
```

### Step 3: Poll for replies and classify

```python
messages = client.messages.list(inbox_id=inbox.id, labels=["unread"])
for msg in messages.data:
    category = classify_reply(msg.text)  # "interested", "not_interested", etc.
    client.messages.update(
        inbox_id=inbox.id,
        message_id=msg.id,
        add_labels=[category, "replied"],
        remove_labels=["unread"],
    )
```

### Step 4: Follow up

After 48 hours with no reply, the agent sends a follow-up. Labels track how many follow-ups each candidate has received.

### Full code

The complete working agent is ~150 lines: [github.com/agentmail-to/recruiter-coordinator](https://github.com/agentmail-to/recruiter-coordinator)

### What's next

- Add webhook support instead of polling for real-time response handling
- Use thread-level tracking with `client.inboxes.threads.list()` for better conversation management
- Deploy as a long-lived process with Docker

---

## X Thread (7 tweets)

**Tweet 1:**
I built an AI recruiting agent that gets its own email inbox and handles outreach autonomously.

150 lines of Python. Open source.

Here's how it works:

**Tweet 2:**
Step 1: The agent creates its own email address via @AgentMailTo.

No Gmail credentials. No OAuth. Just `client.inboxes.create()` and it has an address candidates can reply to.

**Tweet 3:**
Step 2: Feed it a CSV of candidates. It generates personalized outreach with GPT-4o-mini and sends from its own address.

Each email gets labeled "outreach" for tracking.

**Tweet 4:**
Step 3: The agent polls its inbox for replies. When one arrives, it classifies the response:

- Interested
- Not interested
- Question
- Scheduling request

Labels update automatically.

**Tweet 5:**
Step 4: No reply after 48 hours? The agent sends a follow-up. Configurable delay, max follow-ups per candidate.

All tracked through AgentMail labels.

**Tweet 6:**
Why give the agent its own inbox instead of using yours?

- Your inbox stays clean
- Candidates see a real reply-to address
- Multiple agents, multiple inboxes, no conflicts

**Tweet 7:**
Full repo: github.com/agentmail-to/recruiter-coordinator

Stack: Python + AgentMail + OpenAI
Setup: pip install, add API keys, run

Open source, MIT licensed.
