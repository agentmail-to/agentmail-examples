# Email Agent Example

Build an agent that automatically replies to emails

## Requirements

- Python 3.11 or higher
- [AgentMail API key](https://agentmail.io)
- [OpenAI API key](https://platform.openai.com)
- [Ngrok account](https://ngrok.com) to receive webhooks

## Setup

### Ngrok

1. Sign up for a free Ngrok account at [ngrok.com](https://ngrok.com)
2. Get your Ngrok auth token
3. Claim your free static domain

This will create a persistent domain (your-subdomain.ngrok.io) that you can use to receive AgentMail webhooks.

### Config

Create a `.env` file with the following content:

```sh
AGENTMAIL_API_KEY=your-agentmail-api-key
OPENAI_API_KEY=your-openai-api-key
NGROK_AUTHTOKEN=your-ngrok-authtoken

INBOX_USERNAME=your-inbox-username
WEBHOOK_DOMAIN=your-webhook-domain
```

Export enivornment variables in `.env` file

```sh
export $(grep -v '^#' .env | xargs)
```

### AgentMail

Create inbox

```sh
curl -X POST https://api.agentmail.to/v0/inboxes \
     -H "Authorization: Bearer $AGENTMAIL_API_KEY" \
     -H "Content-Type: application/json" \
     -d "{
  \"username\": \"$INBOX_USERNAME\",
  \"display_name\": \"Email Agent\"
}"
```

Create webhook

```sh
curl -X POST https://api.agentmail.to/v0/webhooks \
     -H "Authorization: Bearer $AGENTMAIL_API_KEY" \
     -H "Content-Type: application/json" \
     -d "{
  \"url\": \"https://$WEBHOOK_DOMAIN/webhooks\"
}"
```

### Install

```sh
uv venv
source .venv/bin/activate
uv pip install .
```

## Run

Start the server

```sh
python main.py
```

Finally, send an email to `your-inbox-username@agentmail.to` and wait for a response.
