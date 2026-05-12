# AgentMail Mastra Template

A Mastra agent template with built-in email capabilities via AgentMail. The agent can create inboxes, send and receive emails, and manage threads as part of its tool set. Built with TypeScript, Mastra, and the AgentMail SDK.

## What It Does

- Mastra agent with AgentMail tools: `createInbox`, `sendEmail`, `listMessages`, `replyToMessage`
- The agent decides when to use email based on the conversation
- Supports multi-turn conversations where the agent checks its inbox and responds
- Ready to extend with additional Mastra tools and integrations

![Demo](assets/demo.gif)

## Why This Exists

Mastra is a popular TypeScript agent framework. This template gives any Mastra agent email capabilities in minutes. Instead of building email plumbing, drop in these tools and your agent can send, receive, and manage email threads.

## Prerequisites

- Node.js 18+
- [AgentMail](https://agentmail.to) API key
- [OpenAI](https://platform.openai.com) API key (for the Mastra agent's LLM)

## Install

```bash
git clone https://github.com/agentmail-to/agentmail-mastra-template.git
cd agentmail-mastra-template
npm install
cp .env.example .env
# Add your API keys to .env
```

## Quickstart

```bash
npm run start
```

The agent will start in interactive mode. Try:

- "Create a new inbox for customer outreach"
- "Send an email to test@example.com about the project update"
- "Check my inbox for new messages"
- "Reply to the latest message with a thank you"

## Project Structure

```
src/
  index.ts           - Entry point, starts the agent
  agent.ts           - Mastra agent configuration
  tools/
    agentmail.ts     - AgentMail tools for the agent
```

## How to Deploy

Run as a service, integrate into an API, or use with Mastra's built-in server mode.

```bash
npm run build
node dist/index.js
```

## Docs

- [AgentMail TypeScript SDK](https://docs.agentmail.to/sdks/typescript)
- [Mastra Documentation](https://mastra.ai/docs)
- [Creating Inboxes](https://docs.agentmail.to/api-reference/inboxes/create-inbox)
- [Sending Messages](https://docs.agentmail.to/api-reference/messages/send-message)

## License

MIT
