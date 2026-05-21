# AgentMail Examples

Build AI agents with their own email inboxes. Requires an [AgentMail](https://agentmail.to) API key — [sign up free](https://console.agentmail.to).

## Examples

### Getting Started

| Example | Description |
|---|---|
| [LangChain Terminal](./langchain-terminal) | Chat with a LangChain agent with AgentMail tools via terminal |
| [OpenAI Terminal](./openai-terminal) | Chat with an OpenAI agent with AgentMail tools via terminal |

### Advanced

| Example | Description |
|---|---|
| [Email Agent](./email-agent) | Agent that responds autonomously via email |
| [Sales Agent](./sales-agent) | Agent that sells products to prospects via email |
| [Dinner Agent](./dinner-agent) | Agent that coordinates dinner plans via email |
| [GitHub Maintainer Agent](./github-maintainer-agent) | Agent that manages GitHub issues and PRs via email |

### Templates

Production-ready agent templates. Each has matching Python + TypeScript implementations and is tested end-to-end against real AgentMail + Claude APIs. Featured at [agentmail.to/build/templates](https://agentmail.to/build/templates).

**Productivity**

| Example | Description |
|---|---|
| [Scheduling Agent](./scheduling-agent) | Books meetings via email with calendar invite (.ics) attachments |
| [Inbox Zero](./inbox-zero) | Drafts replies, flags what needs you, sends a morning digest |
| [Note Taker](./note-taker) | Forward emails — they become Markdown notes you can search |
| [Approval Inbox](./approval-inbox) | Your inbox is your approval queue. Configure once, approve everything from email |

**Sales & Outbound**

| Example | Description |
|---|---|
| [GTM Agent](./gtm-agent) | Cold outbound + warm-reply handoff to your sales team |
| [Sales Signal Router](./sales-signal-router) | Triage inbound sales mail. Ping Slack. EOD digest |
| [Negotiation Agent](./negotiation-agent) | Multi-party negotiator for used cars, apartments, B2B contracts |

**Support**

| Example | Description |
|---|---|
| [Support Agent](./support-agent) | Auto-respond to support tickets, escalate when stuck |
| [Docs Assistant](./docs-assistant) | Answers product questions by web-searching your docs (cited) |

**Finance**

| Example | Description |
|---|---|
| [Invoice Processor](./invoice-processor) | Claude PDF vision extracts invoices, matches POs, auto-approves under limit |
| [x402 Payment Agent](./x402-payment-agent) | Vendor invoices land in inbox. Allowlisted vendors auto-pay via x402 |

**Marketing & Personal**

| Example | Description |
|---|---|
| [Newsletter Digest](./newsletter-digest) | Summarizes daily newsletter blasts into one morning digest |
| [Dinner Reservation](./dinner-reservation) | Books dinner reservations end-to-end (2-thread orchestration) |
| [Browser Signup Agent](./browser-signup-agent) | Sign up for anything on the web + handle OTP / verification links |

## Quick Start

```bash
# Clone the repo
git clone https://github.com/agentmail-to/agentmail-examples.git
cd agentmail-examples

# Set your API key
export AGENTMAIL_API_KEY=am_us_xxx

# Run an example
cd email-agent
pip install -r requirements.txt
python main.py
```

To pull just one template (without the whole monorepo):

```bash
npx degit agentmail-to/agentmail-examples/sales-signal-router my-signal-router
cd my-signal-router/python
pip install -r requirements.txt && python agent.py

### Template Agents
 
Production-shaped reference agents. Each lives in its own subfolder and can be pulled
out as a standalone project in one command:
 
```bash
npx degit agentmail-to/agentmail-examples/<template-name> my-new-app
```
 
| Template | What it does |
|---|---|
| [agentmail-approval-inbox](./agentmail-approval-inbox) | Human-in-the-loop approval flow for agent actions |
| [agentmail-browser-signup-agent](./agentmail-browser-signup-agent) | Browser agent that handles email signups end-to-end |
| [agentmail-dinner-reservation](./agentmail-dinner-reservation) | Concierge agent that books restaurant tables via email |
| [agentmail-docs-assistant](./agentmail-docs-assistant) | Answers questions about your docs over email |
| [agentmail-gtm-agent](./agentmail-gtm-agent) | Go-to-market outreach agent |
| [agentmail-inbox-zero](./agentmail-inbox-zero) | Triage and zero out an overloaded inbox |
| [agentmail-invoice-processor](./agentmail-invoice-processor) | Parses invoices from email and routes them |
| [agentmail-negotiation-agent](./agentmail-negotiation-agent) | Negotiates via email on your behalf |
| [agentmail-newsletter-digest](./agentmail-newsletter-digest) | Summarizes newsletter subscriptions into a digest |
| [agentmail-note-taker](./agentmail-note-taker) | Captures and organizes notes from email threads |
| [agentmail-sales-signal-router](./agentmail-sales-signal-router) | Routes inbound sales signals to the right person |
| [agentmail-scheduling-agent](./agentmail-scheduling-agent) | Schedules meetings via email |
| [agentmail-support-agent](./agentmail-support-agent) | Customer support agent over email |
| [agentmail-x402-payment-agent](./agentmail-x402-payment-agent) | Handles x402 payments via email |
| [collections-agent](./collections-agent) | Polite, persistent collections follow-up |
| [contract-redline-agent](./contract-redline-agent) | Redlines contracts received via email |
| [cold-email-researcher](./cold-email-researcher) | Research + cold outreach in one loop |
| [hiring-screener-agent](./hiring-screener-agent) | Screens inbound applicants |
| [legal-intake-agent](./legal-intake-agent) | Intake form-via-email for legal practices |
| [podcast-booking-agent](./podcast-booking-agent) | Books podcast guests / appearances |
| [receipt-parser-agent](./receipt-parser-agent) | Extracts receipt data from forwarded email |
| [recruiter-coordinator](./recruiter-coordinator) | Coordinates candidate scheduling with recruiters |
 
> Looking for the previous repo URLs? They're archived but still accessible -
> the contents now live in this monorepo.
```

## Links

- [AgentMail](https://agentmail.to) — The email API for AI agents
- [Documentation](https://docs.agentmail.to)
- [Python SDK](https://github.com/agentmail-to/agentmail-python)
- [TypeScript SDK](https://github.com/agentmail-to/agentmail-node)
- [Discord](https://discord.gg/ZYN7f7KPjS)
