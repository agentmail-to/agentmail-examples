# Crosspost Plan: Hiring Screener Agent

## Show HN Post

**Title:** Show HN: AI hiring screener that interviews candidates via email

**Body:**
Built an agent that screens job applicants through email. Post its email as the application address. When someone applies, it sends personalized screening questions, scores the responses, and forwards qualified candidates to the hiring manager.

The screening questions are generated based on the applicant's background, not generic. The scoring considers technical fit, communication quality, and your configured criteria.

Unqualified candidates get a polite rejection. Qualified ones get forwarded with a summary and score.

Python, AgentMail (https://agentmail.to) + OpenAI.

Repo: https://github.com/agentmail-to/hiring-screener-agent

---

## Dev.to Article

**Title:** Build an AI Hiring Screener That Interviews Candidates via Email

**Tags:** python, ai, hiring, automation

---

The first filter in hiring is the most repetitive. Every applicant needs the same 3-5 questions answered before a human should look at them. This agent handles that filter.

### Flow

1. Candidate emails the agent to apply
2. Agent sends personalized screening questions
3. Candidate replies with answers
4. Agent scores responses and decides: advance or reject
5. Qualified candidates forwarded to hiring manager with summary

Full code: [github.com/agentmail-to/hiring-screener-agent](https://github.com/agentmail-to/hiring-screener-agent)

---

## X Thread (5 tweets)

**Tweet 1:**
Built an AI agent that screens job applicants via email. Sends personalized questions, scores responses, forwards qualified candidates.

**Tweet 2:**
Post the agent's email as your application address. It handles the first filter so hiring managers only see pre-qualified candidates.

**Tweet 3:**
Questions are personalized based on the applicant's background, not generic templates. Scoring considers technical fit and communication.

**Tweet 4:**
Qualified candidates get forwarded with a score and summary. Unqualified get a polite rejection. All automatic.

**Tweet 5:**
Repo: github.com/agentmail-to/hiring-screener-agent

Python, MIT. Built on @AgentMailTo.
