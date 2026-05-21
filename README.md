# Contract Redline Agent

An AI agent that receives contracts via email, reviews them against your standard terms, and replies with redline suggestions. Built with AgentMail and OpenAI.

## What It Does

- Creates a contract review inbox
- Monitors for incoming emails with contract text or attachments
- Compares contract clauses against your configured standard terms
- Identifies risky clauses: unlimited liability, auto-renewal, non-compete, IP assignment
- Replies with a redline summary: what to accept, what to push back on, and suggested language
- Labels threads: `reviewed`, `high-risk`, `acceptable`, `needs-negotiation`

![Demo](assets/demo.gif)

## Why This Exists

Contract review is slow and expensive. This agent provides a first-pass review in seconds, flagging the clauses that need human attention. It does not replace legal counsel but it makes the review process faster by highlighting what matters.

## Prerequisites

- Python 3.10+
- [AgentMail](https://agentmail.to) API key
- [OpenAI](https://platform.openai.com) API key

## Install

```bash
git clone https://github.com/agentmail-to/contract-redline-agent.git
cd contract-redline-agent
pip install -r requirements.txt
cp .env.example .env
```

## Quickstart

1. Edit `standard_terms.json` with your preferred contract terms.

2. Run:

```bash
python src/main.py
```

Forward a contract to the agent's email. It replies with a redline summary.

## How to Deploy

```bash
docker build -t contract-redline-agent .
docker run --env-file .env contract-redline-agent
```

## Docs

- [AgentMail Python SDK](https://docs.agentmail.to/sdks/python)
- [Replying to Messages](https://docs.agentmail.to/api-reference/messages/reply-to-message)
- [Attachments](https://docs.agentmail.to/api-reference/messages/get-attachment)

## License

MIT
