# AgentMail Examples

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Working examples of AI agents with email capabilities, powered by [AgentMail](https://agentmail.to).

Each example is a self-contained project you can clone and run. All you need is an [AgentMail API key](https://console.agentmail.to).

## Examples

### Getting Started

| Example | Description | Framework |
|---------|-------------|-----------|
| [LangChain Terminal](./langchain-terminal) | Chat with a LangChain agent that can send and receive emails, via a terminal interface | LangChain |
| [OpenAI Terminal](./openai-terminal) | Chat with an OpenAI agent with full email capabilities, via a terminal interface | OpenAI Agents SDK |

### Production Patterns

| Example | Description | Framework |
|---------|-------------|-----------|
| [Email Agent](./email-agent) | Autonomous agent that monitors its inbox and responds to emails in real-time using webhooks | OpenAI |
| [Sales Agent](./sales-agent) | Outbound sales agent that prospects, sends personalized cold emails, and handles replies | OpenAI |

## Quick Start

```bash
# Clone the repo
git clone https://github.com/agentmail-to/agentmail-examples.git
cd agentmail-examples

# Pick an example
cd email-agent

# Set your API keys
export AGENTMAIL_API_KEY=am_us_xxx
export OPENAI_API_KEY=sk-xxx

# Install and run
pip install -r requirements.txt
python main.py
```

## Want to Build Your Own?

- [AgentMail Docs](https://docs.agentmail.to) — full API reference
- [AgentMail Toolkit](https://github.com/agentmail-to/agentmail-toolkit) — pre-built framework integrations
- [AI Email Agent Template](https://github.com/agentmail-to/ai-email-agent-template) — one-click Replit template

## Links

- [AgentMail Website](https://agentmail.to)
- [Console](https://console.agentmail.to)
- [Python SDK](https://github.com/agentmail-to/agentmail-python)
- [TypeScript SDK](https://github.com/agentmail-to/agentmail-node)
- [MCP Server](https://github.com/agentmail-to/agentmail-mcp)

## License

MIT
