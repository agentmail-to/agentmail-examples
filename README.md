# Receipt Parser Agent

An AI agent that receives forwarded receipt emails, extracts line items and totals, and compiles expense reports. Built with AgentMail and OpenAI.

## What It Does

- Creates an expense inbox (e.g., `expenses@agentmail.to`)
- Monitors for forwarded receipt emails
- Extracts vendor, date, line items, tax, and total with GPT-4o-mini
- Categorizes expenses: `travel`, `meals`, `software`, `supplies`, `other`
- Sends a weekly expense summary to a configured recipient
- Labels receipts: `parsed`, `categorized`, `reported`

![Demo](assets/demo.gif)

## Why This Exists

Expense tracking is a chore. Forward your receipts to the agent as they come in. It parses them automatically and sends you a clean summary at the end of the week. No apps, no photos, just forward the email.

## Prerequisites

- Python 3.10+
- [AgentMail](https://agentmail.to) API key
- [OpenAI](https://platform.openai.com) API key

## Install

```bash
git clone https://github.com/agentmail-to/receipt-parser-agent.git
cd receipt-parser-agent
pip install -r requirements.txt
cp .env.example .env
```

## Quickstart

```bash
python src/main.py
```

Forward any receipt email to the agent's address. It parses the receipt and adds it to your running expense report.

## Configuration

- `REPORT_RECIPIENT`: email to receive weekly summaries
- `REPORT_DAY`: day of week to send summary (default: `friday`)

## How to Deploy

```bash
docker build -t receipt-parser-agent .
docker run --env-file .env receipt-parser-agent
```

## Docs

- [AgentMail Python SDK](https://docs.agentmail.to/sdks/python)
- [Listing Messages](https://docs.agentmail.to/api-reference/messages/list-messages)
- [Labels](https://docs.agentmail.to/features/labels)

## License

MIT
