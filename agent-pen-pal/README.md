# Agent Pen Pal

Two AI agents that email each other autonomously, having an ongoing conversation on a topic you choose. Built with AgentMail and OpenAI.

## What It Does

- Creates two inboxes, one per agent, each with a distinct personality
- Agent A sends the first message on a configured topic
- Agent B receives, reads, and replies with its own perspective
- The conversation continues back and forth indefinitely
- Each agent maintains context from the full thread
- Labels track the conversation: `sent`, `received`, `turn-N`

![Demo](assets/demo.gif)

## Why This Exists

A demonstration of agent-to-agent communication over email. Shows how two independent agents can maintain a coherent, multi-turn conversation using standard email infrastructure. Useful for testing multi-agent architectures, generating synthetic conversations, and exploring emergent agent behavior.

## Prerequisites

- Python 3.10+
- [AgentMail](https://agentmail.to) API key
- [OpenAI](https://platform.openai.com) API key

## Install

```bash
git clone https://github.com/agentmail-to/agent-pen-pal.git
cd agent-pen-pal
pip install -r requirements.txt
cp .env.example .env
```

## Quickstart

```bash
python src/main.py
```

Watch two agents debate, discuss, or collaborate via email in real time.

## Configuration

Edit `config.json`:
- `topic`: the conversation topic
- `agent_a.personality`: Agent A's persona
- `agent_b.personality`: Agent B's persona
- `max_turns`: how many exchanges before stopping
- `delay_seconds`: pause between turns

## How to Deploy

```bash
docker build -t agent-pen-pal .
docker run --env-file .env agent-pen-pal
```

## Docs

- [AgentMail Python SDK](https://docs.agentmail.to/sdks/python)
- [Sending Messages](https://docs.agentmail.to/api-reference/messages/send-message)
- [Threading](https://docs.agentmail.to/api-reference/threads)

## License

MIT
