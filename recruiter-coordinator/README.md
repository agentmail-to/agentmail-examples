# Recruiter Coordinator Agent

An AI recruiting agent that manages candidate outreach, scheduling, and follow-ups through its own email inbox. Built with AgentMail and OpenAI.

## What It Does

This agent gets its own email address via [AgentMail](https://agentmail.to) and autonomously handles the recruiting pipeline:

- Sends personalized outreach emails to candidates from a CSV
- Monitors its inbox for replies using polling
- Classifies responses (interested, not interested, question, scheduling request)
- Sends follow-ups to non-responders after a configurable delay
- Labels threads by stage: `outreach`, `replied`, `scheduled`, `rejected`

![Demo](assets/demo.gif)

## Why This Exists

Recruiting coordinators spend most of their time on repetitive email. This agent handles the volume work (outreach, follow-ups, classification) so humans can focus on the conversations that matter.

## Prerequisites

- Python 3.10+
- An [AgentMail](https://agentmail.to) API key ([get one here](https://app.agentmail.to))
- An [OpenAI](https://platform.openai.com) API key

## Install

```bash
git clone https://github.com/agentmail-to/recruiter-coordinator.git
cd recruiter-coordinator
pip install -r requirements.txt
cp .env.example .env
# Add your API keys to .env
```

## Quickstart

1. Add candidates to `candidates.csv` (columns: `name`, `email`, `role`, `company`).

2. Run the agent:

```bash
python src/main.py
```

The agent will:
- Create a dedicated inbox (e.g., `recruiter-bot@agentmail.to`)
- Send outreach to each candidate
- Poll for replies every 60 seconds
- Classify and label each response
- Send follow-ups after 48 hours of no reply

## Configuration

Edit `src/config.py` to adjust:

- `FOLLOW_UP_DELAY_HOURS`: hours before sending follow-up (default: 48)
- `POLL_INTERVAL_SECONDS`: inbox check frequency (default: 60)
- `MAX_FOLLOW_UPS`: maximum follow-ups per candidate (default: 2)

## How to Deploy

Run as a long-lived process on any server, VM, or container:

```bash
# With Docker
docker build -t recruiter-coordinator .
docker run --env-file .env recruiter-coordinator

# Or with systemd, supervisor, etc.
nohup python src/main.py &
```

## Docs

- [AgentMail Python SDK](https://docs.agentmail.to/sdks/python)
- [Creating Inboxes](https://docs.agentmail.to/api-reference/inboxes/create-inbox)
- [Sending Messages](https://docs.agentmail.to/api-reference/messages/send-message)
- [Labels](https://docs.agentmail.to/features/labels)

## License

MIT
