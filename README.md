# AgentMail Examples

Build agents with email inboxes. Requires an [AgentMail](https://agentmail.to) API key.

## Getting Started

1. Get an API key at [agentmail.to](https://agentmail.to)
2. Clone this repo: `git clone https://github.com/agentmail-to/agentmail-examples.git`
3. Pick an example, follow its README

## Examples

### Starter Templates

| Example | Language | Description |
|---------|----------|-------------|
| [OpenAI Terminal](./openai-terminal) | Python | Chat with an OpenAI agent with AgentMail tools via terminal |
| [LangChain Terminal](./langchain-terminal) | Python | Chat with a LangChain agent with AgentMail tools via terminal |
| [Next.js Starter](./nextjs-agentmail-starter) | TypeScript | Next.js 14 app with inbox dashboard, send/receive, and webhook handling |
| [Mastra Template](./agentmail-mastra-template) | TypeScript | Mastra agent with AgentMail tools for inbox, send, list, and reply |

### Sales & Outreach

| Example | Language | Description |
|---------|----------|-------------|
| [Sales Agent](./sales-agent) | Python | Agent that sells products to prospects via email |
| [Cold Email Researcher](./cold-email-researcher) | Python | Research prospects by domain, generate personalized outreach, handle replies |
| [Podcast Booking Agent](./podcast-booking-agent) | Python | Pitch podcast hosts, classify replies, send calendar links to interested hosts |

### Recruiting

| Example | Language | Description |
|---------|----------|-------------|
| [Recruiter Coordinator](./recruiter-coordinator) | Python | Full pipeline: candidate outreach, reply classification, follow-ups |
| [Hiring Screener Agent](./hiring-screener-agent) | Python | Receive applications, send screening questions, score and route candidates |

### Customer Support & Operations

| Example | Language | Description |
|---------|----------|-------------|
| [Email Agent](./email-agent) | Python | Agent that responds autonomously via email |
| [Collections Agent](./collections-agent) | Python | Escalating payment reminders with reply handling and dispute escalation |
| [Legal Intake Agent](./legal-intake-agent) | Python | Intake questionnaire, case classification, attorney routing |
| [Receipt Parser Agent](./receipt-parser-agent) | Python | Forward receipts, extract vendor/items/total, generate weekly expense reports |
| [Contract Redline Agent](./contract-redline-agent) | Python | Forward contracts, flag risky clauses, suggest alternatives |

### Utilities & Fun

| Example | Language | Description |
|---------|----------|-------------|
| [CC the Agent](./cc-the-agent) | Python | CC an agent on any email for summaries, action items, or draft replies |
| [OAuth Reset Handler](./oauth-reset-handler) | Python | Temporary inbox to receive and extract OTP codes, magic links, reset URLs |
| [Email to CLI](./email-to-cli) | Python | Send commands via email subject, get stdout back as a reply |
| [Voice to Email](./voice-to-email) | Python | Record audio, transcribe with Whisper, send as email |
| [Agent Pen Pal](./agent-pen-pal) | Python | Two AI agents with distinct personalities emailing each other |
| [Dinner Agent](./dinner-agent) | Python | Agent that helps coordinate dinner plans via email |
| [GitHub Maintainer Agent](./github-maintainer-agent) | Python | Agent that helps manage GitHub repos via email notifications |

## Resources

- [AgentMail Docs](https://docs.agentmail.to)
- [Python SDK](https://pypi.org/project/agentmail/)
- [TypeScript SDK](https://www.npmjs.com/package/agentmail)
- [API Reference](https://docs.agentmail.to/api-reference)
