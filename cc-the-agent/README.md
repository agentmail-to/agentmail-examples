# CC the Agent

An AI agent that you CC on emails to get instant analysis, action items, or follow-up drafts. Just add it to the CC line of any email. Built with AgentMail and OpenAI.

## What It Does

- Creates an assistant inbox (e.g., `assistant@agentmail.to`)
- Monitors for emails where it is CC'd
- Analyzes the email thread and generates a helpful response
- Replies directly to you (not reply-all) with: summary, action items, suggested reply draft, or research
- Configurable response modes: `summarize`, `action-items`, `draft-reply`, `research`

![Demo](assets/demo.gif)

## Why This Exists

Sometimes you just need a quick take on an email. CC the agent and it replies to you privately with a summary, action items, or a draft reply. No context switching, no copying text into a chat window.

## Prerequisites

- Python 3.10+
- [AgentMail](https://agentmail.to) API key
- [OpenAI](https://platform.openai.com) API key

## Install

```bash
git clone https://github.com/agentmail-to/cc-the-agent.git
cd cc-the-agent
pip install -r requirements.txt
cp .env.example .env
```

## Quickstart

1. Run:

```bash
python src/main.py
```

2. CC the agent's email address on any email.

3. The agent replies directly to you with analysis.

## Configuring Response Mode

Set `DEFAULT_MODE` in `.env`:
- `summarize`: 3-sentence summary
- `action-items`: bullet list of action items
- `draft-reply`: suggested reply you can edit and send
- `auto`: agent picks the most useful response type

Or put the mode in the subject prefix: `[action-items] Original Subject`.

## How to Deploy

```bash
docker build -t cc-the-agent .
docker run --env-file .env cc-the-agent
```

## Docs

- [AgentMail Python SDK](https://docs.agentmail.to/sdks/python)
- [Sending Messages](https://docs.agentmail.to/api-reference/messages/send-message)
- [Labels](https://docs.agentmail.to/features/labels)

## License

MIT
