# Dinner Agent Webhook Example

A simple example showing how to build a group dinner organizer using AgentMail's Webhook API.

## What It Does

1. **Receives dinner requests** - Organizers email the agent to start planning
2. **Collects RSVPs** - Tracks confirmations from guests
3. **Auto-books restaurant** - When threshold is met, picks a restaurant and books
4. **Notifies everyone** - Sends confirmation details to all participants

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Configure

Create `.env` file:

```
AGENTMAIL_API_KEY=your_agentmail_key
NGROK_AUTHTOKEN=your_ngrok_token
NGROK_DOMAIN=your-domain.ngrok-free.app
INBOX_USERNAME=dinner-agent
MIN_CONFIRMATIONS=3
PORT=8080
```

### 3. Run

```bash
python main.py
```

You'll see:
```
Dinner Agent starting...
[INFO] Configuration:
  • Username: dinner-agent
  • Min confirmations: 3
  • Port: 8080
[SUCCESS] ✓ Inbox created: dinner-agent@agentmail.to
[SUCCESS] ✓ Ngrok tunnel: https://your-domain.ngrok-free.app
[SUCCESS] ✓ Webhook registered
============================================================
Dinner Agent Ready!
Email: dinner-agent@agentmail.to
Webhook: https://your-domain.ngrok-free.app/webhook
Min confirmations: 3
============================================================
```

## How It Works

### Workflow

```
[Organizer sends request]
        |
        v
[Agent creates event, confirms to organizer]
        |
        v
[Guests send RSVPs]  -----> [Agent tracks count]
        |                           |
        |                           v
        |                   [Threshold met?]
        |                      /        \
        |                    No          Yes
        |                    |            |
        |                    v            v
        |            [Wait for more]  [Book restaurant]
        |                                 |
        v                                 v
[Agent sends RSVP confirmations]  [Send booking to ALL]
```

### Example Emails

**1. Organizer sends dinner request:**
```
To: dinner-agent@agentmail.to
Subject: Team Dinner
Body: Please organize dinner for 6 people on Friday at 7pm
```

**2. Agent replies to organizer:**
```
Thanks for organizing dinner!

Event Details:
• Party size: 6 people
• Preferred day: Friday
• Preferred time: 7pm

Current RSVPs: 1/3 (you're counted as the organizer!)
```

**3. Guest sends RSVP:**
```
To: dinner-agent@agentmail.to
Subject: Re: Team Dinner
Body: Count me in!
```

**4. When threshold is met, everyone gets:**
```
Your dinner is confirmed!

Restaurant: Thai Garden (Thai cuisine)
Address: 123 Main St, San Francisco
Phone: (555) 123-4567
Date: Friday
Time: 7pm
Party Size: 3 people
Confirmation #: DIN-A1B2C3D4

Attendees:
• Alice (organizer)
• Bob
• Charlie
```

## Code Structure

```
main.py (~690 lines)
├── Imports & Setup
├── Mock Data (restaurants)
├── Helper Functions
│   ├── extract_email() - Parse email addresses
│   ├── extract_dinner_details() - Get party size, day, time
│   ├── is_dinner_request() - Classify as new request
│   └── is_rsvp() - Classify as RSVP
├── State Management
│   ├── create_event() - Initialize dinner event
│   ├── add_participant() - Track RSVPs
│   └── is_ready_to_book() - Check threshold
├── Core Handlers
│   ├── handle_dinner_request() - Process new requests
│   ├── handle_rsvp() - Process confirmations
│   └── book_and_notify() - Book & send confirmations
├── Flask Routes
│   ├── /webhook - Receive email events
│   ├── /health - Health check
│   └── /status - Debug view of events
└── Main Entry Point
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook` | POST | Receives AgentMail webhook events |
| `/health` | GET | Health check (returns `{"status": "healthy"}`) |
| `/status` | GET | Shows all dinner events for debugging |

## Customization

- **MIN_CONFIRMATIONS**: Change how many RSVPs needed before booking
- **RESTAURANTS**: Edit the mock restaurant list in main.py
- **Keywords**: Modify `REQUEST_KEYWORDS` and `RSVP_KEYWORDS` for classification

## Dependencies

```toml
agentmail
flask
python-dotenv
pyngrok
```

## License

MIT
