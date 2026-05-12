# Email to CLI

A bridge that lets you control CLI tools via email. Send an email with a command, and the agent executes it in a sandboxed environment and emails back the output. Built with AgentMail.

## What It Does

- Creates a command inbox
- Monitors for incoming emails containing shell commands
- Executes allowed commands in a sandboxed subprocess
- Emails the output (stdout/stderr) back to the sender
- Supports an allowlist of safe commands
- Labels threads: `executed`, `blocked`, `error`

![Demo](assets/demo.gif)

## Why This Exists

Remote server management via email. When SSH is not available or you need an audit trail of every command, email provides both. Useful for IoT devices, air-gapped systems, or as a quick remote exec interface for agents.

## Prerequisites

- Python 3.10+
- [AgentMail](https://agentmail.to) API key

## Install

```bash
git clone https://github.com/agentmail-to/email-to-cli.git
cd email-to-cli
pip install -r requirements.txt
cp .env.example .env
```

## Quickstart

```bash
python src/main.py
```

Email the agent with a subject like `ls -la /tmp` and it will reply with the output.

## Security

Commands run in a restricted subprocess with:
- An allowlist of permitted commands (configurable in `config.py`)
- Timeout per command (default: 30s)
- No shell expansion by default
- Sender allowlist to restrict who can send commands

**Do not run this in production without reviewing the security configuration.**

## How to Deploy

```bash
docker build -t email-to-cli .
docker run --env-file .env email-to-cli
```

## Docs

- [AgentMail Python SDK](https://docs.agentmail.to/sdks/python)
- [Listing Messages](https://docs.agentmail.to/api-reference/messages/list-messages)
- [Replying to Messages](https://docs.agentmail.to/api-reference/messages/reply-to-message)

## License

MIT
