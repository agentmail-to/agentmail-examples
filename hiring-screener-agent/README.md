# Hiring Screener Agent

An AI agent that screens job applicants via email. It receives applications, asks screening questions, scores responses, and forwards qualified candidates to the hiring manager. Built with AgentMail and OpenAI.

## What It Does

- Creates a hiring inbox (e.g., `apply@agentmail.to`)
- Receives applications and sends a set of screening questions
- Scores candidate responses against configurable criteria
- Forwards qualified candidates to the hiring manager with a summary
- Sends polite rejections to unqualified candidates
- Labels threads: `applied`, `screening`, `qualified`, `rejected`, `forwarded`

![Demo](assets/demo.gif)

## Why This Exists

Screening applicants is the bottleneck in hiring. Most applications need the same 3-5 questions answered before a human needs to look at them. This agent handles that first filter, so hiring managers only see pre-qualified candidates.

## Prerequisites

- Python 3.10+
- [AgentMail](https://agentmail.to) API key
- [OpenAI](https://platform.openai.com) API key

## Install

```bash
git clone https://github.com/agentmail-to/hiring-screener-agent.git
cd hiring-screener-agent
pip install -r requirements.txt
cp .env.example .env
```

## Quickstart

1. Edit `job_config.json` with the role details and screening questions.

2. Run:

```bash
python src/main.py
```

Post the agent's email as the application address. It screens candidates automatically.

## How to Deploy

```bash
docker build -t hiring-screener-agent .
docker run --env-file .env hiring-screener-agent
```

## Docs

- [AgentMail Python SDK](https://docs.agentmail.to/sdks/python)
- [Sending Messages](https://docs.agentmail.to/api-reference/messages/send-message)
- [Threading](https://docs.agentmail.to/api-reference/threads)

## License

MIT
