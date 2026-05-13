# Next.js AgentMail Starter

A Next.js starter template for building AI email agents with AgentMail. Includes inbox creation, message sending, webhook handling, and a dashboard UI. Built with Next.js 14, TypeScript, and the AgentMail SDK.

## What It Does

- Dashboard to view and manage agent inboxes
- API routes for creating inboxes, sending messages, and listing threads
- Webhook endpoint for real-time message handling
- Simple UI to compose and send emails from agent inboxes
- Ready to deploy on Vercel

![Demo](assets/demo.gif)

## Why This Exists

The fastest way to build an email-enabled AI agent with a web interface. Fork this, add your agent logic, and deploy. Handles all the AgentMail plumbing so you can focus on the agent behavior.

## Prerequisites

- Node.js 18+
- [AgentMail](https://agentmail.to) API key

## Install

```bash
git clone https://github.com/agentmail-to/nextjs-agentmail-starter.git
cd nextjs-agentmail-starter
npm install
cp .env.example .env.local
# Add your AGENTMAIL_API_KEY to .env.local
```

## Quickstart

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). You will see a dashboard where you can:

1. Create a new agent inbox
2. View threads for any inbox
3. Compose and send emails
4. See incoming messages in real time (via polling or webhooks)

## Project Structure

```
src/
  app/
    page.tsx              - Dashboard UI
    api/
      agentmail/
        inboxes/route.ts  - Create and list inboxes
        send/route.ts     - Send messages
        threads/route.ts  - List threads
        webhook/route.ts  - Webhook handler for incoming messages
```

## How to Deploy

### Vercel (recommended)

1. Push to GitHub
2. Import in Vercel
3. Add `AGENTMAIL_API_KEY` to environment variables
4. Deploy

### Other platforms

Any platform that supports Next.js: Railway, Render, Fly.io, Docker.

## Webhook Setup

To receive real-time notifications of incoming messages:

1. Deploy the app
2. Set your webhook URL in the AgentMail dashboard to `https://your-domain.com/api/agentmail/webhook`

## Docs

- [AgentMail TypeScript SDK](https://docs.agentmail.to/sdks/typescript)
- [Webhooks](https://docs.agentmail.to/features/webhooks)
- [Creating Inboxes](https://docs.agentmail.to/api-reference/inboxes/create-inbox)
- [Next.js Documentation](https://nextjs.org/docs)

## License

MIT
