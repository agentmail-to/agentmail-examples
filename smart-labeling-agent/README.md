# Smart Email Labeling Agent

An AI-powered email classification agent that automatically analyzes incoming emails across multiple dimensions and applies intelligent labels for automated inbox organization.

## Overview

This agent showcases AgentMail's **labeling feature** as a powerful tool for email automation. It uses OpenAI's GPT-4o-mini to intelligently classify each incoming email across **4 dimensions** and automatically applies structured labels for:

- **Inbox automation** - Auto-route emails to the right team
- **Priority management** - Surface urgent issues immediately
- **Sentiment tracking** - Monitor customer satisfaction
- **Analytics** - Track support trends and metrics

### Why Multi-Dimensional Labeling is Powerful

Instead of a single label like "support" or "urgent", this agent applies **4 labels per email**, creating a rich classification system:

```
Email: "Your product crashed and I lost my work! Need help ASAP!"

Applied Labels:
  ✓ sentiment-negative
  ✓ category-bug-report
  ✓ priority-urgent
  ✓ department-technical

Result: Automatically routed to technical team, flagged as urgent,
        tracked as negative sentiment for customer success analysis.
```

This multi-dimensional approach enables sophisticated workflows like:
- Alert manager when `priority-urgent` + `sentiment-negative`
- Route `department-sales` + `priority-high` to sales team immediately
- Track `sentiment-positive` + `category-praise` for testimonials
- Generate reports on `category-bug-report` trends

## Real-World Use Cases

**Customer Support Teams:**
- Auto-triage incoming tickets by priority and category
- Route emails to specialized teams (billing, technical, sales)
- Track sentiment trends to measure customer satisfaction
- Identify urgent issues before they escalate

**Sales Teams:**
- Automatically flag high-priority leads
- Identify demo requests and pricing inquiries
- Segment warm leads vs. cold inquiries
- Track outreach campaign performance

**Product Teams:**
- Collect and categorize feature requests
- Monitor bug reports and technical issues
- Analyze sentiment around product launches
- Prioritize roadmap based on customer feedback

**Analytics & Reporting:**
- Generate dashboards showing support ticket distribution
- Track response times by priority level
- Measure customer sentiment over time
- Identify trends in feature requests and complaints

## Features

- **Multi-Dimensional Classification**: Analyzes emails across 4 dimensions
  - **Sentiment**: positive, neutral, negative
  - **Category**: question, complaint, feature-request, bug-report, praise
  - **Priority**: urgent, high, normal, low
  - **Department**: sales, support, billing, technical

- **AI-Powered Analysis**: Uses OpenAI GPT-4o-mini for intelligent classification
- **Automatic Label Application**: Labels applied instantly via AgentMail API
- **Retry Logic**: Automatically retries up to 3 times on AI failures
- **Strict Validation**: Validates all classification values against expected sets
- **Real-Time Processing**: Webhook-based instant classification
- **Robust Error Handling**: Graceful failures, individual label retry, clear logging
- **Production Ready**: Idempotent setup, type hints, comprehensive error handling

## Prerequisites

Before you begin, make sure you have:

- **Python 3.8 or higher** installed on your system
- **[AgentMail API Key](https://docs.agentmail.to/quickstart#step-3-create-an-api-key)** - Sign up at [agentmail.to](https://agentmail.to)
- **[OpenAI API Key](https://platform.openai.com/api-keys)** - For AI-powered classification
- **[Ngrok account](https://ngrok.com)** (free tier works)
  - Get your authtoken from [ngrok dashboard](https://dashboard.ngrok.com/get-started/your-authtoken)
  - Claim a free static domain from [ngrok domains](https://dashboard.ngrok.com/cloud-edge/domains)

## Quick Start

### 1. Navigate to the Project

```bash
cd agentmail-examples/smart-labeling-agent
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**Using a virtual environment?** We recommend it!

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
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

You'll need to fill in:

| Variable | Description | Where to Get It |
|----------|-------------|-----------------|
| `AGENTMAIL_API_KEY` | Your AgentMail API key | [AgentMail Dashboard](https://docs.agentmail.to/quickstart) |
| `OPENAI_API_KEY` | Your OpenAI API key | [OpenAI Platform](https://platform.openai.com/api-keys) |
| `NGROK_AUTHTOKEN` | Your ngrok auth token | [Ngrok Dashboard](https://dashboard.ngrok.com/get-started/your-authtoken) |
| `WEBHOOK_DOMAIN` | Your ngrok static domain | [Ngrok Domains](https://dashboard.ngrok.com/cloud-edge/domains) |
| `INBOX_USERNAME` | Username for your inbox | Choose any (default: `smart-labels`) |

Example `.env` file:

```env
AGENTMAIL_API_KEY=am_1234567890abcdef
OPENAI_API_KEY=sk-proj-1234567890abcdef
NGROK_AUTHTOKEN=2abcdef1234567890
WEBHOOK_DOMAIN=my-labeling-agent.ngrok-free.app
INBOX_USERNAME=smart-labels
PORT=8080
```

### 4. Run the Agent

```bash
python agent.py
```

You should see output like this:

```
============================================================
🏷️  SMART EMAIL LABELING AGENT
============================================================

🔧 Setting up AgentMail infrastructure...
  ✓ Inbox created: smart-labels@agentmail.to
  ✓ Webhook created

✅ Setup complete!
  📬 Inbox: smart-labels@agentmail.to
  🔗 Webhook: https://my-labeling-agent.ngrok-free.app/webhook/agentmail

🚀 Agent is ready!
📬 Send emails to: smart-labels@agentmail.to
🤖 AI-powered classification: ENABLED

⏳ Waiting for incoming emails...

 * Running on http://127.0.0.1:8080
```

**Success!** Your agent is now running and ready to classify emails. Leave this terminal window open.

## Testing Your Agent

Let's test the agent with different types of emails to see how it classifies them.

### Example 1: Urgent Complaint

**Send this email:**

```
To: smart-labels@agentmail.to
Subject: Product keeps crashing - need immediate help!
Body:
Your product is TERRIBLE! It crashed 3 times today and I lost all
my work. This is completely unacceptable. I need this fixed IMMEDIATELY
or I want a full refund!
```

**Console Output:**

```
============================================================
📧 NEW EMAIL RECEIVED
============================================================
  From: you@example.com
  Subject: Product keeps crashing - need immediate help!
============================================================
🤖 Analyzing with AI...

📊 Classification Results:
  😞 Sentiment: negative
  📋 Category: complaint
  🚨 Priority: urgent
  🏢 Department: support

  🏷️  Applied labels:
    ✓ sentiment-negative
    ✓ category-complaint
    ✓ priority-urgent
    ✓ department-support

✅ Email successfully classified and labeled!
```

**Why this classification?**
- **Sentiment**: negative (words like "terrible", "unacceptable")
- **Category**: complaint (expressing dissatisfaction, requesting refund)
- **Priority**: urgent (keywords "IMMEDIATELY", "crashed 3 times today")
- **Department**: support (product issue requiring customer support)

### Example 2: Feature Request

**Send this email:**

```
To: smart-labels@agentmail.to
Subject: Dark mode would be amazing!
Body:
Hi! I absolutely love your product. I use it every day and it's been
a game-changer for my workflow.

One feature that would make it even better is dark mode support.
My eyes get tired working late, and a dark theme would be perfect.

Keep up the great work!
```

**Console Output:**

```
============================================================
📧 NEW EMAIL RECEIVED
============================================================
  From: you@example.com
  Subject: Dark mode would be amazing!
============================================================
🤖 Analyzing with AI...

📊 Classification Results:
  😊 Sentiment: positive
  📋 Category: feature-request
  📋 Priority: normal
  🏢 Department: technical

  🏷️  Applied labels:
    ✓ sentiment-positive
    ✓ category-feature-request
    ✓ priority-normal
    ✓ department-technical

✅ Email successfully classified and labeled!
```

**Why this classification?**
- **Sentiment**: positive (words like "love", "amazing", "game-changer")
- **Category**: feature-request (suggesting a new feature)
- **Priority**: normal (no urgency indicators)
- **Department**: technical (product feature implementation)

### Example 3: Sales Inquiry

**Send this email:**

```
To: smart-labels@agentmail.to
Subject: Enterprise plan demo request
Body:
Hello,

I'm the CTO of a 500-person company and we're evaluating solutions
for our team. Your product looks promising.

Could we schedule a demo this week? We're looking to make a decision
soon and want to understand your Enterprise features and pricing.

Looking forward to hearing from you.
```

**Console Output:**

```
============================================================
📧 NEW EMAIL RECEIVED
============================================================
  From: you@example.com
  Subject: Enterprise plan demo request
============================================================
🤖 Analyzing with AI...

📊 Classification Results:
  😊 Sentiment: positive
  📋 Category: question
  ⚡ Priority: high
  🏢 Department: sales

  🏷️  Applied labels:
    ✓ sentiment-positive
    ✓ category-question
    ✓ priority-high
    ✓ department-sales

✅ Email successfully classified and labeled!
```

**Why this classification?**
- **Sentiment**: positive (professional, interested tone)
- **Category**: question (inquiring about demo and pricing)
- **Priority**: high (time-sensitive, mentions "soon", "this week")
- **Department**: sales (enterprise plan, demo request, pricing)

### Example 4: Bug Report

**Send this email:**

```
To: smart-labels@agentmail.to
Subject: API returning 500 errors
Body:
Hi team,

I'm getting consistent 500 errors from the /api/v1/users endpoint.
This started happening this morning around 9am EST.

Error message: "Internal Server Error"
Request: GET /api/v1/users?page=5

Can you look into this? It's blocking our integration testing.

Thanks!
```

**Console Output:**

```
============================================================
📧 NEW EMAIL RECEIVED
============================================================
  From: you@example.com
  Subject: API returning 500 errors
============================================================
🤖 Analyzing with AI...

📊 Classification Results:
  😐 Sentiment: neutral
  📋 Category: bug-report
  ⚡ Priority: high
  🏢 Department: technical

  🏷️  Applied labels:
    ✓ sentiment-neutral
    ✓ category-bug-report
    ✓ priority-high
    ✓ department-technical

✅ Email successfully classified and labeled!
```

**Why this classification?**
- **Sentiment**: neutral (factual bug report, no emotion)
- **Category**: bug-report (reporting technical error with details)
- **Priority**: high (blocking work, but not emergency)
- **Department**: technical (API issue requiring engineering)

### Example 5: Thank You Note

**Send this email:**

```
To: smart-labels@agentmail.to
Subject: Thank you for the amazing support!
Body:
Just wanted to say thank you to your support team. Sarah helped me
resolve my issue in under 10 minutes and was incredibly patient and
helpful.

Your product is excellent, but your customer service is what really
sets you apart. Keep it up!
```

**Console Output:**

```
============================================================
📧 NEW EMAIL RECEIVED
============================================================
  From: you@example.com
  Subject: Thank you for the amazing support!
============================================================
🤖 Analyzing with AI...

📊 Classification Results:
  😊 Sentiment: positive
  📋 Category: praise
  📝 Priority: low
  🏢 Department: support

  🏷️  Applied labels:
    ✓ sentiment-positive
    ✓ category-praise
    ✓ priority-low
    ✓ department-support

✅ Email successfully classified and labeled!
```

**Why this classification?**
- **Sentiment**: positive (grateful, complimentary)
- **Category**: praise (expressing appreciation)
- **Priority**: low (no action needed, informational)
- **Department**: support (thanking support team)

### Example 6: Billing Question

**Send this email:**

```
To: smart-labels@agentmail.to
Subject: Question about my invoice
Body:
Hi,

I received an invoice for $99 but I thought my plan was $79/month.
Could you help me understand the charges?

Thanks
```

**Console Output:**

```
============================================================
📧 NEW EMAIL RECEIVED
============================================================
  From: you@example.com
  Subject: Question about my invoice
============================================================
🤖 Analyzing with AI...

📊 Classification Results:
  😐 Sentiment: neutral
  📋 Category: question
  📋 Priority: normal
  🏢 Department: billing

  🏷️  Applied labels:
    ✓ sentiment-neutral
    ✓ category-question
    ✓ priority-normal
    ✓ department-billing

✅ Email successfully classified and labeled!
```

**Why this classification?**
- **Sentiment**: neutral (polite inquiry, no frustration)
- **Category**: question (asking for clarification)
- **Priority**: normal (important but not urgent)
- **Department**: billing (invoice and payment question)

## How It Works

### Architecture Overview

```
┌─────────────┐
│  Customer   │
│  sends      │ ──────► ┌──────────────┐
│  email      │         │  AgentMail   │
└─────────────┘         │   Inbox      │
                        └──────┬───────┘
                               │ Webhook
                               │ POST
                               ▼
                        ┌──────────────┐
                        │   Ngrok      │
                        │   Tunnel     │
                        └──────┬───────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  Flask       │
                        │  Server      │
                        └──────┬───────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  OpenAI      │
                        │  Analysis    │
                        └──────┬───────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  Apply       │
                        │  Labels      │
                        └──────────────┘
```

### Processing Flow

1. **Email arrives** at your AgentMail inbox (e.g., `smart-labels@agentmail.to`)

2. **AgentMail triggers webhook** - POSTs email data to your ngrok URL

3. **Webhook handler receives data** - Flask server extracts:
   - Subject line
   - Email body
   - Sender information
   - Message ID and Inbox ID

4. **AI classification** - Sends email to OpenAI GPT-4o-mini with structured prompt:
   - Analyzes sentiment (tone and emotion)
   - Identifies category (intent)
   - Assesses priority (urgency indicators)
   - Routes to department (best team to handle)

5. **Label creation** - Converts classifications to labels:
   ```python
   {
     "sentiment": "negative",
     "category": "complaint",
     "priority": "urgent",
     "department": "support"
   }
   # Becomes:
   ["sentiment-negative", "category-complaint",
    "priority-urgent", "department-support"]
   ```

6. **Label application** - Uses AgentMail API:
   ```python
   client.messages.update(
       inbox_id=inbox_id,
       message_id=message_id,
       add_labels=[labels]
   )
   ```

7. **Logging** - Clear console output with emojis showing results

### Code Structure

```python
# Main Components:

setup_agentmail()
    ├── Creates AgentMail inbox (idempotent)
    ├── Starts ngrok tunnel
    └── Registers webhook

analyze_email(subject, content)
    ├── Sends to OpenAI with classification prompt
    ├── Retries up to 3 times on failure
    └── Returns: {sentiment, category, priority, department}

apply_labels(inbox_id, message_id, classifications)
    ├── Converts classifications to label format
    └── Calls client.inboxes.messages.update(add_labels=[...])

receive_webhook()
    ├── Extracts email data from webhook payload
    ├── Calls analyze_email()
    ├── Calls apply_labels()
    └── Logs results
```

## Customization

### Adding New Label Dimensions

Want to add a 5th dimension like "language"? Here's how:

1. **Update the AI prompt** in `analyze_email()`:

```python
content = f"""Analyze this email across 5 dimensions:

Subject: {subject}
Content: {content}

Classify into:
1. sentiment: positive | neutral | negative
2. category: question | complaint | feature-request | bug-report | praise
3. priority: urgent | high | normal | low
4. department: sales | support | billing | technical
5. language: english | spanish | french | german | other

Return ONLY valid JSON with these exact keys.
"""
```

2. **Update validation** in `analyze_email()`:

```python
required_keys = ["sentiment", "category", "priority", "department", "language"]
```

3. **Update `apply_labels()`**:

```python
labels = [
    f"sentiment-{classifications['sentiment']}",
    f"category-{classifications['category']}",
    f"priority-{classifications['priority']}",
    f"department-{classifications['department']}",
    f"language-{classifications['language']}"
]
```

### Modifying Classification Criteria

Want different priority levels? Update the prompt:

```python
# Instead of: urgent | high | normal | low
# Use: p0 | p1 | p2 | p3

content = f"""
3. priority: p0 | p1 | p2 | p3

Priority definitions:
- p0: System down, blocking production (immediate response needed)
- p1: Major functionality broken (response within 4 hours)
- p2: Minor issue or feature request (response within 24 hours)
- p3: Enhancement or nice-to-have (response within 1 week)
"""
```

### Adding Custom Categories

Want to track specific use cases? Add to the categories:

```python
content = f"""
2. category: question | complaint | feature-request | bug-report |
             praise | refund-request | partnership-inquiry |
             security-concern | data-request
"""
```

## Extending the Agent

### Label-Based Automation

Once emails are labeled, you can build powerful automation on top:

#### Example 1: Urgent Negative Alert

```python
def check_urgent_negative(classifications):
    """Alert manager for urgent negative emails."""
    if (classifications['priority'] == 'urgent' and
        classifications['sentiment'] == 'negative'):

        send_slack_alert(
            channel='#support-urgent',
            message=f"🚨 Urgent negative email received!\n"
                   f"From: {sender_email}\n"
                   f"Subject: {subject}"
        )
```

#### Example 2: High-Value Sales Lead

```python
def handle_sales_lead(classifications):
    """Route high-priority sales inquiries to sales team."""
    if (classifications['department'] == 'sales' and
        classifications['priority'] in ['urgent', 'high']):

        # Send to CRM
        create_crm_lead(
            email=sender_email,
            priority=classifications['priority'],
            source='email-agent'
        )

        # Notify sales team
        send_email(
            to='sales@yourcompany.com',
            subject=f"New {classifications['priority']} priority lead",
            body=f"Review: {inbox_id}/message/{message_id}"
        )
```

#### Example 3: Feature Request Tracking

```python
def track_feature_request(classifications, email_body):
    """Log feature requests to product management tool."""
    if classifications['category'] == 'feature-request':

        create_github_issue(
            repo='yourcompany/product-roadmap',
            title=subject,
            body=email_body,
            labels=['feature-request', 'from-customer']
        )
```

#### Example 4: Sentiment Analytics

```python
# Track sentiment over time
from datetime import datetime

sentiment_log = []

def log_sentiment(classifications, sender_email):
    """Track sentiment for customer health scoring."""
    sentiment_log.append({
        'timestamp': datetime.now(),
        'email': sender_email,
        'sentiment': classifications['sentiment'],
        'priority': classifications['priority']
    })

    # Calculate customer health score
    recent_emails = [
        log for log in sentiment_log
        if log['email'] == sender_email
    ][-10:]  # Last 10 emails

    negative_count = sum(
        1 for log in recent_emails
        if log['sentiment'] == 'negative'
    )

    if negative_count >= 3:
        alert_customer_success_team(sender_email)
```

#### Example 5: Auto-Reply by Category

```python
def send_category_specific_reply(classifications, inbox_id, message_id):
    """Send automated reply based on category."""

    replies = {
        'billing': "Thanks for contacting us about billing. Our billing team will respond within 4 hours.",
        'bug-report': "Thank you for reporting this issue. Our engineering team has been notified.",
        'feature-request': "Thanks for the suggestion! We've added it to our product roadmap.",
        'praise': "Thank you for the kind words! We really appreciate your feedback."
    }

    category = classifications['category']
    if category in replies:
        client.inboxes.messages.reply(
            inbox_id=inbox_id,
            message_id=message_id,
            to=[sender_email],
            text=replies[category]
        )
```

### Querying by Labels

Use AgentMail's label filtering to power dashboards:

```python
# Get all urgent support tickets
urgent_support = client.inboxes.threads.list(
    inbox_id='smart-labels@agentmail.to',
    labels=['priority-urgent', 'department-support']
)

print(f"Found {len(urgent_support)} urgent support tickets")

# Get negative sentiment emails for customer success review
negative_emails = client.inboxes.threads.list(
    inbox_id='smart-labels@agentmail.to',
    labels=['sentiment-negative']
)

# Get all feature requests from this quarter
feature_requests = client.inboxes.threads.list(
    inbox_id='smart-labels@agentmail.to',
    labels=['category-feature-request']
)
```

### Building a Dashboard

Create a simple analytics dashboard:

```python
def generate_report():
    """Generate daily classification report."""

    # Fetch all emails from today
    threads = client.inboxes.threads.list(
        inbox_id='smart-labels@agentmail.to'
    )

    # Count by dimension
    stats = {
        'sentiment': {'positive': 0, 'neutral': 0, 'negative': 0},
        'priority': {'urgent': 0, 'high': 0, 'normal': 0, 'low': 0},
        'category': {
            'question': 0, 'complaint': 0, 'feature-request': 0,
            'bug-report': 0, 'praise': 0
        },
        'department': {'sales': 0, 'support': 0, 'billing': 0, 'technical': 0}
    }

    # Aggregate stats (extract from labels)
    for thread in threads:
        for message in thread.messages:
            for label in message.labels:
                dimension, value = label.split('-', 1)
                if dimension in stats and value in stats[dimension]:
                    stats[dimension][value] += 1

    # Print report
    print("\n📊 Daily Email Classification Report")
    print("="*50)
    print(f"\nSentiment Distribution:")
    for sentiment, count in stats['sentiment'].items():
        print(f"  {sentiment}: {count}")

    print(f"\nPriority Distribution:")
    for priority, count in stats['priority'].items():
        print(f"  {priority}: {count}")

    print(f"\nTop Categories:")
    for category, count in stats['category'].items():
        print(f"  {category}: {count}")

    print(f"\nDepartment Load:")
    for dept, count in stats['department'].items():
        print(f"  {dept}: {count}")
```

## Troubleshooting

### Common Issues

#### "ModuleNotFoundError: No module named 'agentmail'"

**Solution**: Install dependencies

```bash
pip install -r requirements.txt
```

If using a virtual environment, make sure it's activated first:

```bash
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
```

#### "AgentMail API Error: Unauthorized"

**Possible causes**:
- Invalid or missing `AGENTMAIL_API_KEY` in `.env`
- API key doesn't have proper permissions

**Solution**:
1. Check your `.env` file
2. Verify your API key at [AgentMail Dashboard](https://docs.agentmail.to/quickstart)
3. Ensure no extra spaces or quotes around the key
4. Make sure `.env` is in the same directory as `agent.py`

Test your API key:
```python
from agentmail import AgentMail
client = AgentMail()
print(client.inboxes.list())  # Should succeed
```

#### "OpenAI API Error: Invalid API key"

**Possible causes**:
- Invalid or missing `OPENAI_API_KEY` in `.env`
- API key doesn't have credits

**Solution**:
1. Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. Update `OPENAI_API_KEY` in `.env`
3. Check your OpenAI account has credits/billing enabled

#### "Ngrok authentication failed"

**Solution**:

1. Get your auth token from [ngrok dashboard](https://dashboard.ngrok.com/get-started/your-authtoken)
2. Update `NGROK_AUTHTOKEN` in `.env`
3. Verify the token has no extra spaces

Alternatively, configure ngrok globally:
```bash
ngrok config add-authtoken YOUR_TOKEN
```

#### Webhook not receiving emails

**Checklist**:
- ✅ Is the agent running? (`python agent.py`)
- ✅ Is ngrok tunnel active? (check console output)
- ✅ Does the webhook URL match your ngrok domain?
- ✅ Did you send email to the correct inbox address?

**Debug steps**:

1. Test if webhook is accessible:
```bash
curl https://your-domain.ngrok-free.app/webhook/agentmail
# Should return: Method Not Allowed (expected - webhooks only accept POST)
```

2. Check ngrok dashboard for requests:
   - Visit [ngrok dashboard](https://dashboard.ngrok.com)
   - View request logs to see if webhooks are arriving

3. Verify webhook is registered:
```python
from agentmail import AgentMail
client = AgentMail()
webhooks = client.webhooks.list()
print(webhooks)
```

#### Labels not being applied

**Check console for errors**:

Look for messages like:
```
❌ Failed to apply labels: ...
```

**Common causes**:

1. **Invalid message_id or inbox_id** - Ensure they're being extracted correctly
2. **API permissions** - Verify your API key has label management permissions
3. **Rate limiting** - OpenAI or AgentMail API rate limits

**Debug**:

Add logging to see the full payload:
```python
print(f"Debug: inbox_id={inbox_id}, message_id={message_id}")
print(f"Debug: labels={labels}")
```

Test label application directly:
```python
client.messages.update(
    inbox_id="your-inbox@agentmail.to",
    message_id="test-message-id",
    add_labels=["test-label"]
)
```

#### AI classification is slow

**Causes**:
- OpenAI API latency
- Large email bodies

**Solutions**:

1. **Truncate long emails**:
```python
def analyze_email(subject, content):
    # Limit content length
    content = content[:2000]  # First 2000 characters
    # ... rest of function
```

2. **Use streaming** (for real-time feedback):
```python
response = openai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...],
    stream=True  # Enable streaming
)
```

3. **Switch to faster model** (less accurate but faster):
```python
model="gpt-3.5-turbo"  # Faster, cheaper, less accurate
```

#### Port 8080 already in use

**Solution 1**: Kill the process using the port

```bash
# macOS/Linux
lsof -ti:8080 | xargs kill -9

# Windows
netstat -ano | findstr :8080
taskkill /PID <PID> /F
```

**Solution 2**: Use a different port

Update `.env`:
```env
PORT=8081
```

#### AI classification is inaccurate

**Causes**:
- Prompt needs tuning for your use case
- Email content is ambiguous

**Solutions**:

1. **Improve the prompt**:
```python
# Add more specific instructions
content = f"""You are an expert at classifying customer support emails.

Context: We are a B2B SaaS company selling project management software.

Classify this email:
Subject: {subject}
Content: {content}

Guidelines:
- "bug-report" = technical malfunction with error messages
- "complaint" = dissatisfaction without technical details
- "feature-request" = explicitly asking for new functionality
...
"""
```

2. **Increase temperature for creative classification**:
```python
temperature=0.5  # More creative (was 0.3)
```

3. **Use better model**:
```python
model="gpt-4o"  # More accurate but more expensive
```

4. **Add examples in prompt** (few-shot learning):
```python
content = f"""Classify emails like these examples:

Example 1:
Email: "Your software deleted my files!"
Classification: {{"sentiment": "negative", "category": "bug-report", "priority": "urgent", "department": "technical"}}

Example 2:
Email: "How much is the Enterprise plan?"
Classification: {{"sentiment": "neutral", "category": "question", "priority": "high", "department": "sales"}}

Now classify this email:
Subject: {subject}
Content: {content}
"""
```

## Project Structure

```
smart-labeling-agent/
├── agent.py                # Main application (~250 lines)
│                           # - Setup AgentMail inbox and webhook
│                           # - AI-powered email classification
│                           # - Retry logic and validation
│                           # - Label application logic
│                           # - Webhook endpoint handler
│
├── requirements.txt        # Python dependencies
│                           # - agentmail (AgentMail SDK)
│                           # - flask (Web server)
│                           # - ngrok (Tunnel service)
│                           # - python-dotenv (Environment variables)
│                           # - openai (AI classification)
│
├── .env.example            # Environment variables template
│                           # Copy to .env and fill in credentials
│
├── .gitignore             # Git ignore rules
│                           # Prevents committing .env and cache
│
└── README.md              # This file
```

## Code Overview

### Main Functions

**1. `setup_agentmail()`**
- Creates or retrieves AgentMail inbox
- Starts ngrok tunnel for webhook
- Registers webhook with AgentMail
- Uses `client_id` for idempotency

**2. `analyze_email(subject, content)`**
- Sends email to OpenAI GPT-4o-mini
- Uses structured JSON output
- Returns classification dict with 4 dimensions
- Retries up to 3 times on failure
- Validates all classification values

**3. `apply_labels(inbox_id, message_id, classifications)`**
- Converts classifications to label format
- Calls `client.inboxes.messages.update(add_labels=[...])`
- Handles errors gracefully with retry logic
- Tries individual labels if batch fails

**4. `receive_webhook()`**
- Flask endpoint for AgentMail webhooks
- Extracts email data
- Orchestrates analysis and labeling
- Returns 200 status always (webhooks best practice)

## Performance Considerations

### API Rate Limits

**OpenAI**:
- Free tier: 3 requests/minute
- Paid tier: 3,500 requests/minute (gpt-4o-mini)

**AgentMail**:
- No rate limits on label operations
- Webhook delivery is instant

### Cost Analysis

**OpenAI pricing** (gpt-4o-mini):
- $0.150 per 1M input tokens
- $0.600 per 1M output tokens

**Average cost per email**:
- ~500 input tokens (email + prompt): $0.000075
- ~100 output tokens (classification): $0.000060
- **Total: ~$0.000135 per email** (~$0.14 per 1000 emails)

For 10,000 emails/month: ~$1.35/month in OpenAI costs

### Optimization Tips

1. **Batch processing**: If you don't need real-time, batch multiple emails
2. **Caching**: Cache classifications for similar emails
3. **Truncation**: Limit email body to first 1000 characters
4. **Model selection**: gpt-4o-mini is 60x cheaper than gpt-4

## Next Steps

### Learn More

- [AgentMail Documentation](https://docs.agentmail.to)
- [AgentMail Python SDK Reference](https://docs.agentmail.to/api)
- [Labels API Guide](https://docs.agentmail.to/core-concepts/labels)
- [OpenAI API Documentation](https://platform.openai.com/docs)

### Join the Community

- [Discord Community](https://discord.gg/hTYatWYWBc) - Get help and share your projects
- [GitHub Issues](https://github.com/agentmail-to/agentmail-docs/issues) - Report bugs or request features

### Explore More Examples

Check out other examples in the [agentmail-examples](../) directory:

- **[auto-reply-agent](../auto-reply-agent/)** - Automated email responses
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

If you build something cool with this agent, we'd love to hear about it! Share in our [Discord community](https://discord.gg/hTYatWYWBc).
