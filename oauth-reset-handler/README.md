# OAuth Reset Handler

An AI agent that handles password reset and OAuth verification flows via email. It creates temporary inboxes to receive OTPs, verification links, and reset codes, then extracts and returns them programmatically. Built with AgentMail.

## What It Does

- Creates a temporary inbox for each verification flow
- Sends password reset or OAuth verification requests
- Polls the inbox for verification emails
- Extracts OTPs, magic links, and reset codes from email bodies
- Returns extracted credentials to the calling application
- Cleans up temporary inboxes after use

![Demo](assets/demo.gif)

## Why This Exists

AI agents that interact with web services need to handle email-based verification. OAuth flows, password resets, and magic links all require receiving an email and extracting a code. This agent provides a reusable pattern for handling these flows programmatically.

## Prerequisites

- Python 3.10+
- [AgentMail](https://agentmail.to) API key
- [OpenAI](https://platform.openai.com) API key (for extraction)

## Install

```bash
git clone https://github.com/agentmail-to/oauth-reset-handler.git
cd oauth-reset-handler
pip install -r requirements.txt
cp .env.example .env
```

## Quickstart

```python
from src.main import get_verification_code

# Create a temp inbox, trigger a reset, wait for the code
code = get_verification_code(
    service_name="example.com",
    trigger_url="https://example.com/forgot-password",
    email_field_id="email",
)
print(f"Verification code: {code}")
```

Or run the demo:

```bash
python src/main.py
```

## How to Deploy

Use as a library in your agent pipeline, or run standalone for testing.

## Docs

- [AgentMail Python SDK](https://docs.agentmail.to/sdks/python)
- [Creating Inboxes](https://docs.agentmail.to/api-reference/inboxes/create-inbox)
- [Listing Messages](https://docs.agentmail.to/api-reference/messages/list-messages)

## License

MIT
