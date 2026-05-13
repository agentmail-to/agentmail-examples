# Crosspost Plan: Agent Pen Pal

## Show HN Post

**Title:** Show HN: Two AI agents having an email conversation with each other

**Body:**
Made two AI agents with distinct personalities that email each other about a topic you choose. Each gets its own inbox via AgentMail (https://agentmail.to), and they maintain a multi-turn conversation over real email.

It is partly a demo of agent-to-agent communication over standard email infrastructure, and partly a way to generate interesting synthetic conversations.

The conversation is configurable: set the topic, personalities, number of turns, and delay between messages. Watch a pragmatic engineer and a philosophical researcher debate AI memory in real time.

Python, ~150 lines.

Repo: https://github.com/agentmail-to/agent-pen-pal

---

## Dev.to Article

**Title:** Build Two AI Agents That Email Each Other

**Tags:** python, ai, agents, experiment

---

What happens when two AI agents with different personalities have an email conversation?

This tutorial builds a system where two agents, each with their own email address, exchange messages back and forth on a topic you configure.

### Why email?

Email is the universal communication protocol. If agents can communicate over email, they can interact with each other and with humans using the same infrastructure. No custom APIs, no message brokers, just email.

### The setup

Each agent gets an inbox from AgentMail. Agent A sends the first message. Agent B reads it, generates a reply in character, and responds. The conversation continues until a configured limit.

Full code: [github.com/agentmail-to/agent-pen-pal](https://github.com/agentmail-to/agent-pen-pal)

---

## X Thread (5 tweets)

**Tweet 1:**
Built two AI agents that email each other. Each has its own inbox, its own personality, and they debate topics autonomously.

**Tweet 2:**
Configure the topic and personalities. A pragmatic engineer vs. a philosophical researcher discussing AI memory. Real email threads, real agent-to-agent communication.

**Tweet 3:**
Each agent maintains context from the full thread history. Conversations are coherent, multi-turn, and sometimes surprising.

**Tweet 4:**
Built on @AgentMailTo. Each agent gets a real inbox. The emails are standard SMTP, viewable from any email client.

**Tweet 5:**
Repo: github.com/agentmail-to/agent-pen-pal

Python, ~150 lines. MIT licensed.
