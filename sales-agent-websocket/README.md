# Sales Agent WebSocket Example

A simple example showing how to build a sales agent using AgentMail's WebSocket API for real-time email processing.

## What It Does

1. **Connects to AgentMail via WebSocket** - receives emails instantly (no webhooks needed!)
2. **Handles Sales Manager emails** - extracts prospect info and sends sales pitches
3. **Responds to Prospects** - answers questions and notifies manager of interest signals
4. **Maintains conversation context** - tracks email threads for coherent discussions

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Configure

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

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
🚀 Sales Agent starting...
📬 Inbox: sales-agent@agentmail.to
✓ Connected! Listening for emails...
```

## How to Use

### Sales Manager Flow

Send an email to your agent with prospect information:

```
To: sales-agent@agentmail.to
Subject: New Lead - AI Product
Body: Please contact john@example.com about our AI chatbot product.
```

The agent will:
1. Extract the prospect email (john@example.com)
2. Generate a personalized sales pitch using AI
3. Send the pitch to the prospect
4. Reply to you confirming what was sent

### Prospect Flow

When John replies with questions:

```
From: john@example.com
Subject: Re: Introduction - AI Product
Body: This sounds interesting. What's the pricing?
```

The agent will:
1. Answer the question using AI
2. If John shows strong interest or disinterest, notify you
3. Maintain conversation context for follow-up emails

## Example Interactions

**Manager → Agent:**
```
"Contact sarah@startup.io about our project management tool.
Tell her it helps teams collaborate better."
```

**Agent → Prospect:**
```
Hi Sarah,

I wanted to introduce you to our project management tool...
[AI-generated sales pitch]

Best regards,
AgentMail Sales Agent
```

**Prospect → Agent:**
```
"Thanks! Can I see a demo?"
```

**Agent → Prospect:**
```
"Absolutely! I'd be happy to arrange a demo..."
```

**Agent → Manager:**
```
Subject: Update: sarah@startup.io
Prospect sarah@startup.io is showing interest.

Their message: "Thanks! Can I see a demo?"
My response: "Absolutely! I'd be happy to arrange a demo..."
```

## How It Works

1. Connects to AgentMail WebSocket API
2. Subscribes to your inbox for real-time updates
3. When email arrives, determines if it's from:
   - **Sales Manager** (contains keywords like "prospect", "contact")
   - **Prospect** (reply to previous outreach)
4. Uses OpenAI to generate appropriate responses
5. Sends emails and tracks conversation history

## Code Structure

Everything is in `main.py` (~240 lines):

- `main()` - WebSocket connection and event loop
- `handle_new_email()` - Routes emails to appropriate handler
- `handle_manager_email()` - Processes manager requests
- `handle_prospect_email()` - Handles prospect responses
- `get_ai_response()` - Calls OpenAI for intelligent replies
- Simple helpers for sending/replying to emails

## Troubleshooting

**"Error creating inbox"**
- Check your `AGENTMAIL_API_KEY` is correct
- Inbox might already exist (that's fine, agent will use it)

**"OpenAI API error"**
- Verify `OPENAI_API_KEY` is set correctly
- Check you have API credits

**"No response from agent"**
- Check the console for error messages
- Verify email was sent to correct inbox address
- Try sending a simple test email

## Customization

Want to modify the behavior? Edit these parts of `main.py`:

- **Agent personality**: Change `system_prompt` in `get_ai_response()`
- **Intent detection**: Modify `intent_keywords` in `handle_prospect_email()`
- **Manager detection**: Update `is_from_manager()` keywords

## Next Steps

This is a simple example to get started. For production use, consider adding:

- Database for conversation persistence
- More sophisticated intent detection
- Error recovery and reconnection logic
- Rate limiting and quota management
- Logging and monitoring

## License

MIT - feel free to use and modify!
