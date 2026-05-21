# Cold Email Researcher Agent

An AI agent that researches prospects, writes personalized cold emails, and sends them from its own inbox. Built with AgentMail and OpenAI.

## What It Does

This agent automates the research-and-outreach pipeline for B2B sales:

- Takes a list of prospect domains
- Researches each company using web search
- Generates personalized cold emails based on research
- Sends from a dedicated AgentMail inbox
- Tracks opens and replies with labels
- Handles responses intelligently (books calls, answers questions, handles objections)

![Demo](assets/demo.gif)

## Why This Exists

Cold email that converts requires research. Most sales teams skip it because it takes too long. This agent does the research and writes the email in seconds, then manages the entire conversation thread.

## Prerequisites

- Python 3.10+
- [AgentMail](https://agentmail.to) API key
- [OpenAI](https://platform.openai.com) API key

## Install

```bash
git clone https://github.com/agentmail-to/cold-email-researcher.git
cd cold-email-researcher
pip install -r requirements.txt
cp .env.example .env
# Add your API keys to .env
```

## Quickstart

1. Add prospects to `prospects.csv` (columns: `name`, `email`, `company`, `domain`).

2. Run the agent:

```bash
python src/main.py
```

The agent will:
- Create a sales outreach inbox
- Research each prospect's company
- Generate and send a personalized email
- Monitor for replies and classify them
- Respond to interested prospects with calendar links

## How to Deploy

```bash
docker build -t cold-email-researcher .
docker run --env-file .env cold-email-researcher
```

## Docs

- [AgentMail Python SDK](https://docs.agentmail.to/sdks/python)
- [Sending Messages](https://docs.agentmail.to/api-reference/messages/send-message)
- [Replying to Messages](https://docs.agentmail.to/api-reference/messages/reply-to-message)

## License

MIT
