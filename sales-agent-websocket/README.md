# Sales Agent WebSocket Example

A simple example showing how to build a sales agent using AgentMail's WebSocket API for real-time email processing.

## What It Does

1. **Connects to AgentMail via WebSocket** - receives emails instantly (no webhooks needed!)
2. **Handles Sales Manager emails** - extracts prospect info and sends AI-generated sales pitches
3. **Responds to Prospects** - answers questions using AI with conversation context
4. **Detects Intent** - identifies if prospect is interested, not interested, or asking questions
5. **Notifies Manager** - automatically alerts manager when prospects show strong interest signals

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Configure

Create `.env` file with your API keys:

```
AGENTMAIL_API_KEY=your_agentmail_key
OPENAI_API_KEY=your_openai_key
INBOX_USERNAME=sales-agent
```

### 3. Run

```bash
python main.py
```

You'll see:
```
Sales Agent starting...
Inbox: sales-agent@agentmail.to
✓ Connecting to AgentMail WebSocket...
✓ Connected! Listening for emails...
```

## How It Works

### Sales Manager Flow

1. Manager sends email to agent with prospect info:
   ```
   To: sales-agent@agentmail.to
   Subject: New Lead
   Body: Please contact john@example.com about our AI product.
   ```

2. Agent extracts prospect email, generates AI sales pitch, sends to prospect

3. Agent replies to manager confirming what was sent

### Prospect Flow

1. Prospect replies with questions or interest

2. Agent detects intent using keyword matching:
   - **Interested**: "demo", "meeting", "tell me more", "sounds good"
   - **Not interested**: "no thank", "not right now", "maybe later"
   - **Question**: "?", "how", "what", "when", "why"

3. Agent generates AI response and replies to prospect

4. If strong intent signal detected, agent notifies manager:
   ```
   Subject: Update: john@example.com
   Prospect john@example.com is showing interest.

   Their message: "Can I see a demo?"
   My response: "Absolutely! I'd be happy to arrange..."
   ```

## Code Structure

Everything is in `main.py` (~260 lines):

```
main.py
├── Imports & Setup
├── Helper Functions
│   ├── extract_email() - Parse email from "Name <email>" format
│   ├── is_from_manager() - Detect manager emails by keywords
│   └── extract_prospect_info() - Extract prospect email from body
├── AI & Email Functions
│   ├── get_ai_response() - Call OpenAI GPT-4o-mini
│   ├── send_email() - Send new emails
│   └── reply_to_email() - Reply to existing threads
├── Handler Functions
│   ├── handle_manager_email() - Process manager requests
│   ├── handle_prospect_email() - Handle prospects with intent detection
│   └── handle_new_email() - Route emails to appropriate handler
└── Main Function - WebSocket connection loop
```

### WebSocket Connection Pattern

Uses AgentMail SDK's WebSocket client:

```python
from agentmail import AsyncAgentMail
from agentmail.websockets.client import AsyncWebsocketsClient

agentmail = AsyncAgentMail(api_key=api_key)
ws_client = AsyncWebsocketsClient(client_wrapper=agentmail._client_wrapper)

async with ws_client.connect() as socket:
    await socket.send_subscribe(Subscribe(inbox_ids=[inbox_id]))
    async for event in socket:
        if isinstance(event, MessageReceivedEvent):
            await handle_new_email(event.message)
```

## Customization

- **Agent personality**: Edit `system_prompt` in `get_ai_response()`
- **Intent detection**: Modify `intent_keywords` dict in `handle_prospect_email()`
- **Manager detection**: Update keywords in `is_from_manager()`

## Dependencies

```toml
agentmail>=0.0.19
openai>=1.0.0
python-dotenv>=1.0.0
```

## License

MIT
