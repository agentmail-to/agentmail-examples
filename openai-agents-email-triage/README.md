# Email Triage Agent — OpenAI Agents SDK + AgentMail

An autonomous email triage agent built with the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) and [AgentMail](https://agentmail.to).

The agent gets its own email inbox, reads incoming messages, classifies them, and either replies directly, escalates to a human, or skips spam — all autonomously.

## What it does

```
Incoming email → AgentMail inbox → OpenAI Agent triages → Reply / Escalate / Skip
```

1. **Creates an inbox** — The agent provisions its own email address via AgentMail
2. **Polls for new mail** — Checks for unread messages every N seconds
3. **Reads full threads** — Fetches conversation history for context
4. **Triages with tools** — The OpenAI agent classifies and acts using function tools:
   - `reply_to_email` — Confident answer → sends reply + labels the thread
   - `escalate_to_human` — Complex/sensitive → forwards to team + sends holding reply
   - `skip_message` — Spam or auto-reply → marks as skipped
   - `create_draft` — Good reply but wants human review first

## Why AgentMail + OpenAI Agents SDK?

| Capability | What it enables |
|---|---|
| **Dedicated agent inboxes** | Each agent gets its own email address — no shared credentials |
| **Two-way email** | Read, reply, forward — not just send |
| **Thread management** | Full conversation context for every decision |
| **Labels** | Track state (category, escalated, auto-replied) on each message |
| **Drafts** | Create drafts for human review before sending |
| **OpenAI function tools** | Clean tool-use pattern — agent picks the right action |

## Quick start

```bash
cd python
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
python agent.py
```

You'll see:
```
📬 Email triage agent live at: triage-abc123@agentmail.to
   Escalating to: team@yourcompany.com
   Model: gpt-4o
   Polling every 10s. Ctrl-C to stop.
```

Send an email to the printed address and watch it get triaged.

## Configuration

| Variable | Required | Description |
|---|---|---|
| `AGENTMAIL_API_KEY` | ✅ | Get one at [agentmail.to](https://agentmail.to) |
| `OPENAI_API_KEY` | ✅ | OpenAI API key |
| `ESCALATION_EMAIL` | ✅ | Where to forward escalated emails |
| `PRODUCT_NAME` | | Your product name (default: "Acme Corp") |
| `AGENT_NAME` | | Agent's sign-off name (default: "Alex") |
| `OPENAI_MODEL` | | Model to use (default: "gpt-4o") |
| `POLL_INTERVAL_SECONDS` | | Polling frequency (default: 10) |
| `INBOX_USERNAME` | | Custom inbox prefix (default: auto-generated) |

## How it works

The agent uses the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) `function_tool` decorator to expose AgentMail operations as callable tools. The SDK handles:

- Tool schema generation from Python type hints
- Automatic tool calling and result parsing
- Conversation management

AgentMail handles the email infrastructure:

- Inbox provisioning (instant, API-driven)
- Message polling and thread reconstruction
- Sending replies and forwards
- Label-based state tracking
- Draft management for human-in-the-loop workflows

## Extending this example

- **Add webhooks**: Replace polling with [AgentMail webhooks](https://docs.agentmail.to/webhooks/webhooks-overview) for real-time processing
- **Multi-agent handoffs**: Use the Agents SDK handoff pattern to route emails to specialized agents
- **Knowledge base**: Add a RAG tool so the agent can search your docs before replying
- **Analytics**: Track triage metrics using labels and the AgentMail list API

## More resources

- [AgentMail docs](https://docs.agentmail.to)
- [AgentMail MCP server](https://github.com/agentmail-to/agentmail-mcp)
- [OpenAI Agents SDK docs](https://openai.github.io/openai-agents-python/)
- [AgentMail Python SDK](https://pypi.org/project/agentmail/)
