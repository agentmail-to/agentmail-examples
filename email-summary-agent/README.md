# Email Summary Agent

An AI-powered agent that collects all emails received throughout the day and sends you a comprehensive daily summary using the OpenAI API.

This example is for demo purposes only and is not ready for production.

## Features

- **Automatic Email Collection**: Stores all emails received in your AgentMail inbox
- **AI-Powered Summaries**: Uses OpenAI API to generate intelligent, categorized summaries
- **Daily Schedule**: Sends summaries at a configurable time each day
- **Smart Categorization**: Groups emails by type (urgent, meetings, requests, etc.)
- **Action Items**: Highlights deadlines and tasks that need attention
- **Acknowledgment Messages**: Optionally sends auto-replies to senders
- **Test Data**: Includes 12 sample emails for testing

## Use Cases

- **Executive Digest**: Forward all work emails, get one AI-categorized summary at end of day
- **Newsletter Consolidation**: Route all newsletters to agent's inbox, receive one morning digest with key insights
- **Shared Inbox Monitoring**: Forward info@/hr@ emails, entire team receives morning summary with visibility
- **Sales Pipeline Tracking**: BCC agent on prospect emails, manager gets daily summary of deals and sentiment


## How It Works

```
1. Emails arrive at summary-agent@agentmail.to throughout the day
2. At scheduled time (default 5 PM), agent fetches all emails from inbox
3. AI analyzes all emails and generates a categorized summary
4. Summary email sent to your configured address
```

## Requirements

- Python 3.11 or higher
- [AgentMail API key](https://agentmail.io)
- [OpenAI API key](https://platform.openai.com)
- [Ngrok account](https://ngrok.com) (for receiving webhooks)

## Quick Start

### 1. Get API Keys

You'll need three API keys:

**AgentMail API Key**
- Sign up at [agentmail.io](https://agentmail.io)
- Get your API key from the dashboard

**OpenAI API Key**
- Go to [platform.openai.com](https://platform.openai.com)
- Create an API key
- Make sure you have credits available

**Ngrok Auth Token** (for webhooks)
- Sign up for free at [ngrok.com](https://ngrok.com)
- Get your auth token from [dashboard.ngrok.com](https://dashboard.ngrok.com/get-started/your-authtoken)

### 2. Install Dependencies

```sh
cd email-summary-agent

# Create virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install packages
uv pip install .
```

### 3. Configure Environment

Set your environment variables:

```sh
export AGENTMAIL_API_KEY=your-agentmail-api-key
export OPENAI_API_KEY=your-openai-api-key
export NGROK_AUTHTOKEN=your-ngrok-authtoken
export SUMMARY_RECIPIENT_EMAIL=your-email@example.com

# Optional settings
export INBOX_USERNAME=summary-agent
export SUMMARY_TIME=17:00
export SEND_ACKNOWLEDGMENT=true
```

Or create a `.env` file:

```sh
AGENTMAIL_API_KEY=your-agentmail-api-key
OPENAI_API_KEY=your-openai-api-key
NGROK_AUTHTOKEN=your-ngrok-authtoken
SUMMARY_RECIPIENT_EMAIL=your-email@example.com
INBOX_USERNAME=summary-agent
SUMMARY_TIME=17:00
SEND_ACKNOWLEDGMENT=true
```

Then load it:
```sh
export $(grep -v '^#' .env | xargs)
```

### 4. Run the Agent

```sh
python main.py
```

The agent will automatically:
- ✅ Create the AgentMail inbox (or use existing)
- ✅ Set up ngrok tunnel
- ✅ Create webhook
- ✅ Start collecting emails

You'll see:
```
============================================================
Email Summary Agent Ready!
============================================================
Inbox: summary-agent@agentmail.to
Summary Recipient: your-email@example.com
Daily Summary Time: 17:00
```

### 5. Test the Agent

**Option A: Load Sample Emails (Recommended for Testing)**

Open a **new terminal** and load 12 realistic sample emails:

```sh
# Send sample emails to the inbox (requires API key)
curl -X POST http://localhost:8080/load-samples \
  -H "X-API-Key: $AGENTMAIL_API_KEY"

# Check emails were sent (no authentication required)
curl http://localhost:8080/emails/today

# Generate and send summary immediately (requires API key)
curl -X POST http://localhost:8080/summary/now \
  -H "X-API-Key: $AGENTMAIL_API_KEY"
```

**Check your email!** You should receive an AI-generated summary within 10-30 seconds showing:
- Urgent items (server maintenance)
- Meetings (budget review)
- Action items (security training, invoices)
- Requests (feature requests, PR reviews)

**Option B: Send Real Emails**

Send a test email to your agent's inbox:

**Send to:** `summary-agent@agentmail.to`

The agent will:
1. ✅ Receive the email in its AgentMail inbox
2. ✅ Send acknowledgment (if enabled)
3. ✅ Include it in the next scheduled summary (default 5 PM)

**Trigger summary anytime:**
```sh
curl -X POST http://localhost:8080/summary/now \
  -H "X-API-Key: $AGENTMAIL_API_KEY"
```

## Sending Emails to the Agent

Once the agent is running, send emails to: **`summary-agent@agentmail.to`**

You can send from:
- Your personal email
- Forwarding rules from other inboxes
- BCC on emails you want summarized
- Newsletter subscriptions

**Trigger immediate summary anytime:**
```sh
curl -X POST http://localhost:8080/summary/now \
  -H "X-API-Key: $AGENTMAIL_API_KEY"
```

## Example Summary Email

Here's what the daily summary looks like:

```
From: summary-agent@agentmail.to
To: your-email@example.com
Subject: Daily Email Summary - 2025-11-08

DAILY EMAIL SUMMARY
Friday, November 08, 2025

Total Emails Received: 12

=== URGENT / ACTION REQUIRED ===

🚨 Server Maintenance Tonight (11 PM - 3 AM)
   From: mike.johnson@vendor.com
   Action: Notify team, update status page
   Downtime: 30 minutes expected

⚠️ Security Training Deadline: November 15
   From: security@company.com
   Action: Complete training at training.company.com (45 min)

=== MEETINGS & EVENTS ===

📅 Q4 Budget Review - Tomorrow 2 PM
   From: sarah.chen@techcorp.com
   Location: Conference Room B
   Prep: Spending reports, projections, budget requests

📅 New Employee Orientation - Next Monday
   From: recruiting@company.com
   Action: Introduce yourself to 3 new team members

=== REQUESTS & FOLLOW-UPS ===

💼 Feature Request: Multi-language Support
   From: alex.rivera@client.com
   Action: Schedule call next week (Tue-Thu available)
   Topics: Timeline, languages, pricing

📝 Code Review: PR #247 - Authentication Bug Fix
   From: noreply@github.com
   Action: Review requested from @tech-leads

📋 Contract Review Needed - NDA with NewClient Corp
   From: jessica.thompson@legal.com
   Issues: Confidentiality period, data handling, termination
   Action: Review marked-up document, discuss before responding

=== BUSINESS OPPORTUNITIES ===

🤝 Partnership Proposal from PartnerTech
   From: david.park@partner.com
   Opportunity: Integration with 50K+ users
   Action: Consider intro call

=== FYI / INFORMATIONAL ===

📊 October Marketing Campaign Results
   From: lisa.wong@marketing.com
   Highlights: 45% conversion increase, 67% social engagement growth

💰 Stripe Invoice: $2,450.00 due Nov 15
   From: invoices@stripe.com
   Auto-charge to card ending in 4242

✅ AWS Support Case #12345678 Resolved
   From: support@aws.amazon.com
   Issue: EC2 performance resolved via instance upgrade

🎟️ Early Bird Tickets: Tech Summit 2026
   From: events@industry.org
   Dates: March 15-17, San Francisco
   Savings: $400 (ends Nov 30)

=== ACTION ITEMS SUMMARY ===

Today/Tomorrow:
• Prepare for Q4 budget meeting (2 PM tomorrow)
• Notify team about tonight's server maintenance

This Week:
• Schedule call with alex.rivera@client.com (multi-language feature)
• Review GitHub PR #247
• Review legal contract with jessica.thompson

By November 15:
• Complete security training
• Pay Stripe invoice ($2,450)

Consider:
• Partnership call with PartnerTech
• Tech Summit 2026 early bird registration

---

DETAILED EMAIL LIST

1. [09:15 AM] From: sarah.chen@techcorp.com
   Subject: Q4 Budget Review Meeting - Tomorrow 2 PM

2. [10:30 AM] From: mike.johnson@vendor.com
   Subject: URGENT: Server maintenance window tonight

3. [11:00 AM] From: recruiting@company.com
   Subject: New Employee Orientation - Next Monday

4. [11:45 AM] From: alex.rivera@client.com
   Subject: Feature Request: Multi-language Support

5. [12:20 PM] From: noreply@github.com
   Subject: [ProjectX] Pull Request #247: Fix authentication bug

6. [01:00 PM] From: invoices@stripe.com
   Subject: Invoice for November 2025 - $2,450.00

7. [02:15 PM] From: lisa.wong@marketing.com
   Subject: Campaign Performance Report - October

8. [02:45 PM] From: security@company.com
   Subject: ACTION REQUIRED: Security Training Completion

9. [03:30 PM] From: david.park@partner.com
   Subject: Partnership Proposal - Integration Opportunity

10. [04:00 PM] From: support@aws.amazon.com
    Subject: Your Support Case #12345678 - Resolved

11. [04:30 PM] From: events@industry.org
    Subject: Early Bird Tickets: Tech Summit 2026

12. [04:45 PM] From: jessica.thompson@legal.com
    Subject: Contract Review - NDA with NewClient Corp

---
This summary was generated automatically by Email Summary Agent.
Inbox: summary-agent@agentmail.to
```

## Configuration

### Change Summary Time

Update `.env`:

```sh
SUMMARY_TIME=18:30  # 6:30 PM
```

Time format: HH:MM (24-hour)

### Disable Acknowledgment Emails

By default, the agent sends a brief acknowledgment to every sender:

```
Thank you for your email.

Your message has been received and will be included in today's summary.

This is an automated response from the Email Summary Agent.
```

To disable:

```sh
SEND_ACKNOWLEDGMENT=false
```

### Change Summary Recipient

Update `.env`:

```sh
SUMMARY_RECIPIENT_EMAIL=team@company.com
```

## API Endpoints

**Authentication:** POST endpoints require API key authentication via the `X-API-Key` header. The API key must match the `AGENTMAIL_API_KEY` configured for this agent (ensures only the agent owner can trigger operations).

### Health Check

```
GET /health
```

No authentication required.

Returns:

```json
{
  "status": "healthy",
  "service": "email-summary-agent",
  "emails_today": 12
}
```

### Trigger Summary Now

```
POST /summary/now
```

**Authentication:** Required - Include `X-API-Key` header with your AgentMail API key.

Fetches all emails from the AgentMail inbox and sends a summary immediately.

**Example:**
```sh
curl -X POST http://localhost:8080/summary/now \
  -H "X-API-Key: your-agentmail-api-key"
```

Returns:

```json
{
  "status": "success"
}
```

### Get Today's Emails

```
GET /emails/today
```

No authentication required.

Fetches and returns all emails received today from the AgentMail inbox.

### Load Sample Emails

```
POST /load-samples
```

**Authentication:** Required - Include `X-API-Key` header with your AgentMail API key.

Sends 12 realistic sample emails to the inbox via AgentMail API for testing purposes.

**Example:**
```sh
curl -X POST http://localhost:8080/load-samples \
  -H "X-API-Key: your-agentmail-api-key"
```

Returns:

```json
{
  "status": "success",
  "emails_sent": 12,
  "emails_failed": 0
}
```

## Architecture

```
email-summary-agent/
├── main.py                  # Webhook server and scheduler
├── summary_agent.py         # AI summarization and inbox fetching
├── setup_inbox.py           # Standalone inbox setup script
├── sample_emails.json       # Sample test emails
├── requirements.txt         # Dependencies
└── pyproject.toml          # Package configuration
```

### How It Works

**Email Reception (main.py:48-90)**
- Webhook receives incoming email notifications
- Optionally sends acknowledgment to sender
- Emails are stored in AgentMail inbox

**Sample Email Loading (main.py:131-161)**
- `/load-samples` endpoint reads sample_emails.json
- Sends each sample email to the inbox via AgentMail API
- Useful for testing without needing external email clients

**Daily Scheduler (main.py:164-194)**
- Background thread checks time every minute
- At configured time, triggers summary generation
- Calls summary agent to fetch and summarize emails

**Email Fetching (summary_agent.py:21-56)**
- Fetches all emails from AgentMail inbox for current day
- Uses `inboxes.messages.list()` with date filter
- Retrieves full message content for each email

**AI Summary Generation (summary_agent.py:58-95)**
- Formats emails for GPT-4
- Prompts AI to categorize and summarize
- Highlights urgent items and action items
- Generates structured summary with categories

## Customization

### Modify Summary Format

Edit `summary_agent.py:20-35` to change the AI prompt:

```python
system_prompt = """Your custom instructions here"""
```

### Add Custom Categories

Update the categorization prompt to include your categories:

```python
def generate_category_breakdown(self, emails: List[Dict]) -> Dict:
    system_prompt = """Categorize into: Sales, Support, Engineering, etc."""
```

## Troubleshooting

### Summary Not Sending

1. Check scheduler is running (should see "Summary scheduler started" in logs)
2. Verify `SUMMARY_TIME` format is HH:MM
3. Check `SUMMARY_RECIPIENT_EMAIL` is set
4. Ensure there are emails to summarize

### Emails Not Being Received

1. Verify webhook is receiving email notifications (check logs)
2. Verify AgentMail webhook is configured correctly
3. Check emails are arriving in the AgentMail inbox
4. Test with `/emails/today` endpoint to see what's in the inbox

### OpenAI Errors

1. Verify `OPENAI_API_KEY` is set
2. Check you have API credits
3. Verify using a supported model (gpt-4o)
4. Check API usage limits

## Security Considerations

- **Email Content**: All email content is sent to OpenAI for summarization
- **Storage**: Emails stored in AgentMail inbox (managed by AgentMail)
- **API Authentication**:
  - POST endpoints (`/summary/now`, `/load-samples`) require API key authentication via the `X-API-Key` header
  - Validates that the provided API key has access to the summary-agent inbox using the AgentMail SDK
  - Only users with access to this specific inbox can trigger operations
- **Webhook Endpoint**: `/webhooks` endpoint has no authentication (called by AgentMail service)
- **Data Retention**: Emails persist in AgentMail inbox according to AgentMail's retention policies

For production use:
- Add webhook signature verification to validate requests from AgentMail
- Review AgentMail's data retention and privacy policies
- Consider email content sensitivity before sending to OpenAI
- Secure your AgentMail API key (never commit it to version control, use environment variables)
- Consider adding rate limiting to prevent API abuse
- Consider caching API key validation results to reduce SDK calls on authenticated endpoints

## Advanced Features

### Multiple Summary Recipients

Modify `summary_agent.py` to support multiple recipients in the `send_summary()` method, or create multiple summary agent instances with different recipients.

### Weekly Summaries

Add a weekly summary function to `summary_agent.py`:

```python
def fetch_weekly_emails(self) -> List[Dict]:
    """Fetch all emails from the past 7 days."""
    week_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)

    response = self.agentmail.inboxes.messages.list(
        inbox_id=self.inbox_id,
        after=week_start.isoformat(),
        limit=500
    )

    # Process messages similar to fetch_todays_emails()
    ...
```

### Slack Integration

Send summaries to Slack instead of email:

```python
import requests

def send_to_slack(summary):
    webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
    requests.post(webhook_url, json={"text": summary})
```
