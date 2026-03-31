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

## Links

- [AgentMail](https://agentmail.to) — The email API for AI agents
- [Documentation](https://docs.agentmail.to)
- [Python SDK](https://github.com/agentmail-to/agentmail-python)
- [TypeScript SDK](https://github.com/agentmail-to/agentmail-node)
- [Discord](https://discord.gg/ZYN7f7KPjS)
