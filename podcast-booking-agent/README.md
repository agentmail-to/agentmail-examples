# Podcast Booking Agent

An AI agent that pitches you as a guest on podcasts via email. It researches shows, sends personalized pitches, and manages the booking conversation. Built with AgentMail and OpenAI.

## What It Does

- Creates a booking outreach inbox
- Takes a list of target podcasts with host emails
- Researches each show and generates a personalized pitch
- Sends pitches from the agent's inbox
- Monitors for replies and classifies: `interested`, `declined`, `question`, `scheduling`
- Handles scheduling replies by sharing your calendar link
- Labels threads: `pitched`, `replied`, `booked`, `declined`

![Demo](assets/demo.gif)

## Why This Exists

Getting booked on podcasts is a numbers game. You need to pitch dozens of shows to get a few bookings. This agent handles the outreach at scale, personalizing each pitch based on the show's focus, and manages the back-and-forth so you only step in when a booking is confirmed.

## Prerequisites

- Python 3.10+
- [AgentMail](https://agentmail.to) API key
- [OpenAI](https://platform.openai.com) API key

## Install

```bash
git clone https://github.com/agentmail-to/podcast-booking-agent.git
cd podcast-booking-agent
pip install -r requirements.txt
cp .env.example .env
```

## Quickstart

1. Edit `podcasts.csv` with target shows (columns: `show_name`, `host_name`, `host_email`, `show_topic`).

2. Run:

```bash
python src/main.py
```

## How to Deploy

```bash
docker build -t podcast-booking-agent .
docker run --env-file .env podcast-booking-agent
```

## Docs

- [AgentMail Python SDK](https://docs.agentmail.to/sdks/python)
- [Sending Messages](https://docs.agentmail.to/api-reference/messages/send-message)
- [Replying to Messages](https://docs.agentmail.to/api-reference/messages/reply-to-message)

## License

MIT
