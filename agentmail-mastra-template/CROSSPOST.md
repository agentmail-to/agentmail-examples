# Crosspost Plan: AgentMail Mastra Template

## Show HN Post

**Title:** Show HN: Give any Mastra agent email capabilities with AgentMail

**Body:**
A Mastra template that gives any agent email tools: create inboxes, send messages, list conversations, reply to threads.

Instead of building email plumbing, drop in these tools and your Mastra agent can send and receive email as part of its reasoning loop.

Example: "Create an inbox and send a project update to the team" - the agent creates the inbox, drafts the email, and sends it.

TypeScript, Mastra + AgentMail SDK.

Repo: https://github.com/agentmail-to/agentmail-mastra-template

---

## Dev.to Article

**Title:** Give Your Mastra Agent Email Superpowers with AgentMail

**Tags:** typescript, ai, mastra, email

---

Mastra is one of the fastest-growing TypeScript agent frameworks. But agents need to communicate with the outside world, and email is the universal protocol.

This template adds four email tools to any Mastra agent:

1. **createInbox** - give the agent its own email address
2. **sendEmail** - send from the agent's inbox
3. **listMessages** - check for new messages
4. **replyToMessage** - respond to conversations

### Setup

```bash
npm install agentmail @mastra/core
```

### Using the tools

```typescript
import { Agent } from "@mastra/core/agent";
import { createInbox, sendEmail, listMessages, replyToMessage } from "./tools/agentmail";

const agent = new Agent({
  name: "Email Agent",
  tools: { createInbox, sendEmail, listMessages, replyToMessage },
  // ...
});
```

The agent decides when to use email based on the conversation. Ask it to "send an update to the team" and it will create an inbox, draft the message, and send it.

Full code: [github.com/agentmail-to/agentmail-mastra-template](https://github.com/agentmail-to/agentmail-mastra-template)

---

## X Thread (5 tweets)

**Tweet 1:**
Give any Mastra agent email capabilities with @AgentMailTo.

4 tools: createInbox, sendEmail, listMessages, replyToMessage. Drop in and go.

**Tweet 2:**
The agent decides when to use email. Ask it to "send a project update" and it creates an inbox, drafts the message, and sends.

**Tweet 3:**
Each tool is a standard Mastra tool with Zod input schemas. Clean integration, no hacks.

**Tweet 4:**
TypeScript, Mastra + AgentMail SDK. Interactive CLI included for testing.

**Tweet 5:**
Repo: github.com/agentmail-to/agentmail-mastra-template

npm install && npm run start
