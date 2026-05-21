# Collections Agent

An AI agent that handles payment collection follow-ups via email. It sends payment reminders, escalates overdue accounts, and tracks payment status. Built with AgentMail and OpenAI.

## What It Does

- Creates a collections inbox
- Sends initial payment reminder emails from an invoice list
- Escalates with progressively firmer follow-ups on a schedule
- Classifies replies: `paid`, `dispute`, `payment-plan`, `no-response`
- Tracks each account through the collections pipeline with labels
- Generates summary reports of collection status

![Demo](assets/demo.gif)

## Why This Exists

Chasing overdue invoices is tedious but critical for cash flow. This agent sends consistent, professional reminders on schedule and handles the common responses, so your team only intervenes for disputes and payment plan negotiations.

## Prerequisites

- Python 3.10+
- [AgentMail](https://agentmail.to) API key
- [OpenAI](https://platform.openai.com) API key

## Install

```bash
git clone https://github.com/agentmail-to/collections-agent.git
cd collections-agent
pip install -r requirements.txt
cp .env.example .env
```

## Quickstart

1. Add invoices to `invoices.csv` (columns: `name`, `email`, `amount`, `due_date`, `invoice_id`).

2. Run:

```bash
python src/main.py
```

The agent sends reminders, monitors replies, and escalates automatically.

## How to Deploy

```bash
docker build -t collections-agent .
docker run --env-file .env collections-agent
```

## Docs

- [AgentMail Python SDK](https://docs.agentmail.to/sdks/python)
- [Sending Messages](https://docs.agentmail.to/api-reference/messages/send-message)
- [Labels](https://docs.agentmail.to/features/labels)

## License

MIT
