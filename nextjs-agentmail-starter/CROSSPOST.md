# Crosspost Plan: Next.js AgentMail Starter

## Show HN Post

**Title:** Show HN: Next.js starter for building AI email agents with AgentMail

**Body:**
A Next.js template for building AI agents that send and receive email. Includes API routes for inbox creation, message sending, thread listing, and a webhook endpoint for real-time handling.

Ships with a simple dashboard UI. Fork it, add your agent logic to the webhook handler, deploy to Vercel.

Stack: Next.js 14, TypeScript, AgentMail SDK.

One-click deploy to Vercel. API key as the only env var.

Repo: https://github.com/agentmail-to/nextjs-agentmail-starter

---

## Dev.to Article

**Title:** Build an AI Email Agent with Next.js and AgentMail

**Tags:** nextjs, typescript, ai, email

---

If you are building an AI agent that needs email, you need: inbox creation, message sending, thread management, and real-time webhook handling. This starter template gives you all four as Next.js API routes.

### What you get

- `POST /api/agentmail/inboxes` - create agent inboxes
- `POST /api/agentmail/send` - send messages
- `GET /api/agentmail/threads` - list conversation threads
- `POST /api/agentmail/webhook` - handle incoming messages in real time

### Quick start

```bash
npx create-next-app --example https://github.com/agentmail-to/nextjs-agentmail-starter my-agent
cd my-agent
echo "AGENTMAIL_API_KEY=your_key" > .env.local
npm run dev
```

### Adding agent logic

The webhook handler is where your agent lives. When a message arrives:

```typescript
case "message.received":
  // Classify the message
  // Generate a response with your LLM
  // Reply via the AgentMail SDK
  break;
```

Full code: [github.com/agentmail-to/nextjs-agentmail-starter](https://github.com/agentmail-to/nextjs-agentmail-starter)

---

## X Thread (6 tweets)

**Tweet 1:**
Built a Next.js starter template for AI email agents.

Fork, add your agent logic, deploy to Vercel. Handles all the email plumbing.

**Tweet 2:**
Four API routes:
- Create inboxes
- Send messages
- List threads
- Webhook for real-time incoming messages

Plus a dashboard UI.

**Tweet 3:**
The webhook handler is where your agent lives. Incoming message -> classify -> generate response -> reply. All via the @AgentMailTo SDK.

**Tweet 4:**
One env var: AGENTMAIL_API_KEY. Deploy to Vercel in 30 seconds.

**Tweet 5:**
Stack: Next.js 14, TypeScript, AgentMail SDK. MIT licensed.

**Tweet 6:**
Repo: github.com/agentmail-to/nextjs-agentmail-starter

npm install && npm run dev
