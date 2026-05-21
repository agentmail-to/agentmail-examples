# Auto-Reply Email Agent

A simple, beginner-friendly example of building an email auto-reply agent with AgentMail.

## What it Does

This agent automatically responds to incoming emails with a friendly, personalized message. Perfect for:
- Out-of-office replies
- Acknowledgment receipts
- Basic customer service responses
- Learning how to build with AgentMail

## Features

- Automatic email responses
- Personalized greetings (extracts sender name from email)
- Simple template-based replies (no AI required)
- Easy to customize
- Optional upgrade path to AI-powered replies
- Idempotent setup (safe to run multiple times)

## Prerequisites

Before you begin, make sure you have:

- **Python 3.8 or higher** installed on your system
- **[AgentMail API Key](https://docs.agentmail.to/quickstart#step-3-create-an-api-key)** - Sign up and get your key
- **[Ngrok account](https://ngrok.com)** (free tier works fine)
  - Get your authtoken from the [ngrok dashboard](https://dashboard.ngrok.com/get-started/your-authtoken)
  - Claim a free static domain from [ngrok domains](https://dashboard.ngrok.com/cloud-edge/domains)

## Quick Start

### 1. Navigate to the Project

```bash
cd agentmail-examples/auto-reply-agent
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
nano .env  # or use your preferred editor
```

User'll need to fill in:
- **AGENTMAIL_API_KEY**: Your AgentMail API key
- **NGROK_AUTHTOKEN**: Your ngrok authentication token
- **WEBHOOK_DOMAIN**: Your ngrok static domain (e.g., `your-name.ngrok-free.app`)
- **INBOX_USERNAME**: Choose a username for your inbox (default: `auto-reply`)

### 4. Run the Agent

```bash
python agent.py
```

You should see output like this:

```
============================================================
AUTO-REPLY EMAIL AGENT
============================================================

Setting up AgentMail infrastructure...

Agent is ready!
Inbox: auto-reply@agentmail.to
Webhook: https://your-name.ngrok-free.app/webhooks

Send emails to: auto-reply@agentmail.to

Waiting for incoming emails...

 * Running on http://127.0.0.1:8080
```

## Testing Your Agent

### Send a Test Email

1. From your personal email, send a message to your agent's inbox:

```
To: auto-reply@agentmail.to
Subject: Testing Auto-Reply
Body: Hi, this is a test email!
```

2. Watch the console output. You should see:

```
============================================================
INCOMING EMAIL
============================================================
From: your-email@example.com
Subject: Testing Auto-Reply
============================================================

AUTO-REPLY SENT to your-email@example.com
```

3. Check your inbox for the auto-reply:

```
Hi Your-email,

Thank you for your email! I've received your message and will get back to you within 24 hours.

If your matter is urgent, please reply with "URGENT" in the subject line.

Best regards,
Auto-Reply Agent
```

## Customization

### Change the Reply Template

Edit the `generate_reply()` function in `agent.py`:

```python
def generate_reply(sender_name, original_subject):
    return f"""Hi {sender_name},

    Your custom message here!

    You can use these variables:
    - Sender name: {sender_name}
    - Original subject: {original_subject}

    Best regards,
    Your Agent Name
    """
    ```

### Upgrade to AI-Powered Replies

Want more intelligent, context-aware replies? Follow these steps:

1. **Install OpenAI SDK**:
   ```bash
   pip install openai
   ```

2. **Add your OpenAI API key** to `.env`:
   ```bash
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. **Uncomment the LLM function** in `agent.py`:
   - Find the `generate_llm_reply()` function (around line 70)
   - Uncomment all the code in that function

4. **Update the webhook handler** to use the LLM:
   - In the `receive_webhook()` function (around line 135)
   - Replace this line:
     ```python
     reply_text = generate_reply(sender_name, subject)
     ```
   - With this:
     ```python
     reply_text = generate_llm_reply(sender_name, message.get('text', ''))
     ```

5. **Restart the agent**

Now your agent will use GPT-4 to generate intelligent, contextual auto-replies!

## How It Works

### Setup Phase

1. **Creates an AgentMail inbox** with the username you specified
   - Uses `client_id` for idempotency (won't create duplicates if you run it again)
   - Returns existing inbox if it already exists

2. **Starts an ngrok tunnel** to make your local server accessible
   - Uses your static domain for a consistent webhook URL

3. **Registers a webhook** with AgentMail
   - AgentMail will POST to this webhook whenever an email arrives

### Runtime Phase

When an email arrives:

```
1. Email sent to auto-reply@agentmail.to
          ↓
2. AgentMail receives email
          ↓
3. AgentMail POSTs to your webhook
          ↓
4. Your agent receives webhook
          ↓
5. Extracts sender info (name, email, subject)
          ↓
6. Generates personalized reply
          ↓
7. Sends reply via AgentMail SDK
          ↓
8. Sender receives auto-reply
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'agentmail'"

**Solution**: Install dependencies
```bash
pip install -r requirements.txt
```

### "AgentMail API Error: Unauthorized"

**Possible causes**:
- Invalid or missing `AGENTMAIL_API_KEY` in `.env`
- API key doesn't have proper permissions

**Solution**:
1. Check your `.env` file
2. Verify your API key at [AgentMail Dashboard](https://docs.agentmail.to/quickstart)

### "Ngrok authentication failed"

**Possible causes**:
- Invalid or missing `NGROK_AUTHTOKEN` in `.env`

**Solution**:
1. Get your authtoken from [ngrok dashboard](https://dashboard.ngrok.com/get-started/your-authtoken)
2. Update `.env` with the correct token

### "Webhook not receiving emails"

**Checklist**:
1. ✅ Is the agent running? (`python agent.py`)
2. ✅ Is ngrok tunnel active? (check console output)
3. ✅ Does the webhook URL match your ngrok domain?
4. ✅ Did you send email to the correct inbox address?

**Debug steps**:
```bash
# Check if webhook is accessible
curl https://your-domain.ngrok-free.app/webhooks

# Should return: Method Not Allowed (this is expected - webhooks only accept POST)
```

### "Address already in use" / "Port 8080 is already in use"

**Solution 1**: Kill the process using port 8080
```bash
# On macOS/Linux
lsof -ti:8080 | xargs kill -9

# On Windows
netstat -ano | findstr :8080
taskkill /PID <PID> /F
```

**Solution 2**: Change the port in `agent.py`
```python
PORT = 8081  # Use a different port
```

### Webhook receives the email but doesn't send a reply

**Check**:
1. Look for errors in the console output
2. Verify your `AGENTMAIL_API_KEY` has send permissions
3. Check that `inbox_id` and `message_id` are being extracted correctly

**Debug**:
Add print statements to see the full payload:
```python
import json
print(json.dumps(payload, indent=2))
```

## Project Structure

```
auto-reply-agent/
├── agent.py           # Main application code (~150 lines)
│                      # - Setup AgentMail inbox and webhook
│                      # - Template-based reply generator
│                      # - Webhook endpoint handler
│
├── requirements.txt   # Python dependencies
│                      # - agentmail (AgentMail SDK)
│                      # - flask (Web server)
│                      # - ngrok (Tunnel service)
│                      # - python-dotenv (Environment variables)
│
├── .env.example       # Environment variables template
│                      # Copy to .env and fill in your credentials
│
├── .gitignore        # Git ignore rules
│                      # Prevents committing .env and other sensitive files
│
└── README.md         # This file
```

## Code Overview

### Main Components

**1. Setup Function** (`setup_agentmail()`)
- Creates or retrieves AgentMail inbox
- Starts ngrok tunnel
- Registers webhook
- Uses `client_id` for idempotency

**2. Reply Generator** (`generate_reply()`)
- Simple string template
- Personalizes with sender's name
- No external API calls needed

**3. Webhook Handler** (`receive_webhook()`)
- Receives POST requests from AgentMail
- Extracts email metadata
- Generates and sends auto-reply
- Returns 200 status immediately

## Next Steps

### Learn More
- [AgentMail Documentation](https://docs.agentmail.to)
- [AgentMail Python SDK Reference](https://docs.agentmail.to/api)
- [Webhook Setup Guide](https://docs.agentmail.to/webhooks/webhook-setup)

### Join the Community
- [Discord Community](https://discord.gg/hTYatWYWBc)
- [Report Issues](https://github.com/agentmail-to/agentmail-docs/issues)

### Explore More Examples
Check out other examples in the [agentmail-examples](../) directory:
- **[email-agent](../email-agent/)** - AI-powered email assistant
- **[sales-agent](../sales-agent/)** - Automated sales outreach
- **[dinner-agent](../dinner-agent/)** - Group dinner organizer
- **[github-maintainer-agent](../github-maintainer-agent/)** - GitHub PR/issue bot

## Contributing

Found a bug or want to improve this example? We welcome contributions!

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - feel free to use this as a starting point for your own projects!

---

**Built with ❤️ using [AgentMail](https://agentmail.to)**
