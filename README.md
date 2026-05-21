# Legal Intake Agent

An AI agent that handles initial legal intake via email. It collects case details from potential clients, classifies case types, and routes qualified leads to the right attorney. Built with AgentMail and OpenAI.

## What It Does

- Creates an intake inbox (e.g., `intake@agentmail.to`)
- Responds to initial inquiries with a structured questionnaire
- Extracts case details from client responses
- Classifies case type: `personal-injury`, `employment`, `contract`, `family`, `criminal`, `other`
- Checks for conflicts and statute of limitations concerns
- Routes qualified cases to the appropriate attorney email
- Labels threads by status: `new`, `questionnaire-sent`, `details-received`, `qualified`, `routed`

![Demo](assets/demo.gif)

## Why This Exists

Law firms lose leads because intake is slow. Potential clients email at night and on weekends when no one is there to respond. This agent responds immediately, collects the right information, and routes the case, so attorneys start their day with qualified leads instead of raw inquiries.

## Prerequisites

- Python 3.10+
- [AgentMail](https://agentmail.to) API key
- [OpenAI](https://platform.openai.com) API key

## Install

```bash
git clone https://github.com/agentmail-to/legal-intake-agent.git
cd legal-intake-agent
pip install -r requirements.txt
cp .env.example .env
```

## Quickstart

1. Edit `attorneys.json` with your routing rules.
2. Run:

```bash
python src/main.py
```

Share the agent's email address on your website. It handles the rest.

## How to Deploy

```bash
docker build -t legal-intake-agent .
docker run --env-file .env legal-intake-agent
```

## Docs

- [AgentMail Python SDK](https://docs.agentmail.to/sdks/python)
- [Replying to Messages](https://docs.agentmail.to/api-reference/messages/reply-to-message)
- [Threading](https://docs.agentmail.to/api-reference/threads)

## License

MIT
