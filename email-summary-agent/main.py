"""
Email Summary Agent - Main application entry point.
Collects emails throughout the day and sends daily summaries.
"""

import os
import sys
import threading
import time
from functools import wraps
from datetime import datetime, time as dt_time
from flask import Flask, request, jsonify
from pyngrok import ngrok
from agentmail import AgentMail
from summary_agent import SummaryAgent


# Configuration
AGENTMAIL_API_KEY = os.environ.get("AGENTMAIL_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
NGROK_AUTHTOKEN = os.environ.get("NGROK_AUTHTOKEN")
INBOX_USERNAME = os.environ.get("INBOX_USERNAME", "summary-agent")
WEBHOOK_DOMAIN = os.environ.get("WEBHOOK_DOMAIN")
SUMMARY_RECIPIENT_EMAIL = os.environ.get("SUMMARY_RECIPIENT_EMAIL")
SUMMARY_TIME = os.environ.get("SUMMARY_TIME", "17:00")  # Default 5 PM

# Check required environment variables
if not AGENTMAIL_API_KEY:
    print("Error: AGENTMAIL_API_KEY not set")
    sys.exit(1)

if not OPENAI_API_KEY:
    print("Error: OPENAI_API_KEY not set")
    sys.exit(1)

if not SUMMARY_RECIPIENT_EMAIL:
    print("Error: SUMMARY_RECIPIENT_EMAIL not set")
    sys.exit(1)

# Initialize components
agentmail = AgentMail(api_key=AGENTMAIL_API_KEY)
summary_agent = None  # Will be initialized in setup_infrastructure() with inbox_id
inbox_id = None  # Will be set in setup_infrastructure()

# Flask app for webhook handling
app = Flask(__name__)


def require_api_key(f):
    """Decorator to require API key authentication for endpoints.

    Validates that the provided API key has access to the summary-agent inbox.
    This ensures only users with access to this specific inbox can trigger operations.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for API key in X-API-Key header
        api_key = request.headers.get('X-API-Key')

        if not api_key:
            return jsonify({
                "status": "error",
                "message": "Missing API key. Include X-API-Key header with your AgentMail API key."
            }), 401

        # Validate that the API key has access to the summary-agent inbox
        try:
            # Create AgentMail client with provided API key
            test_client = AgentMail(api_key=api_key)

            # Try to access the summary-agent inbox
            # This will fail if the key doesn't have access to this inbox
            test_client.inboxes.messages.list(
                inbox_id=inbox_id,
                limit=1
            )

            # If we get here, the API key is valid and has access to the inbox
            return f(*args, **kwargs)

        except Exception as e:
            return jsonify({
                "status": "error",
                "message": "Invalid API key or no access to this inbox. Unauthorized."
            }), 403

    return decorated_function


@app.route('/webhooks', methods=['POST'])
def handle_webhook():
    """Handle incoming AgentMail webhooks."""
    try:
        data = request.json
        print(f"\nReceived webhook: {data.get('event_type')}")

        if data.get('event_type') == 'email.received':
            email_data = data.get('data', {})

            # Extract email information
            from_info = email_data.get('from', {})
            from_email = from_info.get('email', 'unknown@example.com')
            subject = email_data.get('subject', 'No Subject')

            print(f"From: {from_email}")
            print(f"Subject: {subject}")
            print("Email received - will be fetched from inbox during summary generation")

            # Send acknowledgment (optional)
            # You can disable this if you don't want auto-replies
            send_acknowledgment = os.environ.get("SEND_ACKNOWLEDGMENT", "true").lower() == "true"
            if send_acknowledgment and inbox_id:
                agentmail.inboxes.messages.send(
                    inbox_id=inbox_id,
                    to=from_email,
                    subject=f"Re: {subject}",
                    text=f"""Thank you for your email.

Your message has been received and will be included in today's summary.

This is an automated response from the Email Summary Agent.
"""
                )
                print(f"Sent acknowledgment to {from_email}")

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"Error processing webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        emails = summary_agent.fetch_todays_emails() if summary_agent else []
        email_count = len(emails)
    except:
        email_count = 0
    return jsonify({
        "status": "healthy",
        "service": "email-summary-agent",
        "emails_today": email_count
    }), 200


@app.route('/summary/now', methods=['POST'])
@require_api_key
def send_summary_now():
    """Manually trigger a summary (useful for testing)."""
    try:
        summary_agent.send_summary()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/emails/today', methods=['GET'])
def get_todays_emails():
    """Get all emails received today."""
    try:
        emails = summary_agent.fetch_todays_emails()
        return jsonify({
            "count": len(emails),
            "emails": emails
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/load-samples', methods=['POST'])
@require_api_key
def load_sample_emails():
    """Send sample emails to the inbox for testing."""
    try:
        import json

        # Read sample emails
        with open('sample_emails.json', 'r') as f:
            sample_emails = json.load(f)

        sent_count = 0
        failed_count = 0

        # Send each sample email to the inbox with retry logic
        # Note: from field will show as the sending inbox, but subject/body contain the sample data
        for email in sample_emails:
            # Include sender info in the body since we can't spoof from address
            full_body = f"From: {email.get('from_name', '')} <{email.get('from_email', '')}>\n\n{email.get('body', '')}"

            # Retry up to 3 times per email
            for attempt in range(3):
                try:
                    agentmail.inboxes.messages.send(
                        inbox_id=inbox_id,
                        to=f"{INBOX_USERNAME}@agentmail.to",
                        subject=email.get('subject', 'No Subject'),
                        text=full_body
                    )
                    sent_count += 1
                    break
                except Exception as send_err:
                    if attempt < 2:
                        print(f"Retry sending email '{email.get('subject')}' (attempt {attempt + 1}/3): {send_err}")
                        time.sleep(1)
                    else:
                        print(f"Failed to send email '{email.get('subject')}' after 3 attempts: {send_err}")
                        failed_count += 1

        print(f"✓ Sent {sent_count}/{len(sample_emails)} sample emails to inbox")
        if failed_count > 0:
            print(f"✗ Failed to send {failed_count} emails")

        return jsonify({
            "status": "success" if failed_count == 0 else "partial",
            "emails_sent": sent_count,
            "emails_failed": failed_count
        }), 200
    except Exception as e:
        print(f"✗ Error loading sample emails: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


def parse_time(time_str: str) -> dt_time:
    """Parse time string in HH:MM format."""
    try:
        hour, minute = map(int, time_str.split(':'))
        return dt_time(hour=hour, minute=minute)
    except:
        print(f"Invalid time format: {time_str}, using default 17:00")
        return dt_time(hour=17, minute=0)


def summary_scheduler():
    """Background thread that sends daily summaries at scheduled time."""
    print(f"Summary scheduler started - will send daily at {SUMMARY_TIME}")

    target_time = parse_time(SUMMARY_TIME)
    last_sent_date = None

    while True:
        try:
            now = datetime.now()
            current_time = now.time()
            current_date = now.date()

            # Check if it's time to send and we haven't sent today yet
            if (current_time.hour == target_time.hour and
                current_time.minute == target_time.minute and
                last_sent_date != current_date):

                print(f"\nSending daily summary at {now}")
                summary_agent.send_summary()
                last_sent_date = current_date
                print("Summary sent!")

            # Sleep for 60 seconds before checking again
            time.sleep(60)

        except Exception as e:
            print(f"Error in summary scheduler: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(60)


def setup_infrastructure():
    """Set up AgentMail inbox and webhook."""

    global summary_agent, inbox_id

    print("\n" + "=" * 60)
    print("Setting up Email Summary Agent")
    print("=" * 60)

    # Create inbox if it doesn't exist
    try:
        inbox = agentmail.inboxes.create(
            username=INBOX_USERNAME,
            domain="agentmail.to",
            display_name="Email Summary Agent"
        )
        inbox_id = inbox.inbox_id
        print(f"✓ Inbox created: {INBOX_USERNAME}@agentmail.to")
        print(f"  Inbox ID: {inbox_id}")
        print(f"  Type: {type(inbox)}")
        print(f"  Inbox object: {inbox}")
    except Exception as e:
        if "already exists" in str(e).lower() or "AlreadyExistsError" in str(e):
            print(f"✓ Inbox already exists: {INBOX_USERNAME}@agentmail.to")
            # Get the inbox_id from existing inbox
            response = agentmail.inboxes.list()
            print(f"  Response type: {type(response)}")
            print(f"  Response: {response}")

            # Find the inbox that matches our username
            for existing_inbox in response.inboxes:
                print(f"  Checking inbox: {existing_inbox}")
                print(f"  Inbox ID: {existing_inbox.inbox_id}")
                # AgentMail uses email address as inbox_id
                if existing_inbox.inbox_id == f"{INBOX_USERNAME}@agentmail.to":
                    inbox_id = existing_inbox.inbox_id
                    print(f"  ✓ Found matching inbox")
                    print(f"  Inbox ID: {inbox_id}")
                    break
            else:
                # If no match found, use the first inbox (fallback)
                if response.inboxes:
                    inbox_id = response.inboxes[0].inbox_id
                    print(f"  Using first inbox as fallback: {inbox_id}")

            if not inbox_id:
                print(f"✗ Error: Could not find inbox_id for {INBOX_USERNAME}")
                raise Exception("Could not retrieve inbox_id")
        else:
            print(f"✗ Error creating inbox: {e}")
            raise

    # Initialize summary agent with inbox_id
    summary_agent = SummaryAgent(agentmail, inbox_id, INBOX_USERNAME, SUMMARY_RECIPIENT_EMAIL)
    print(f"✓ Summary agent initialized")

    # Set up ngrok tunnel if domain not provided
    webhook_url = None
    if WEBHOOK_DOMAIN:
        webhook_url = f"https://{WEBHOOK_DOMAIN}/webhooks"
        print(f"✓ Using provided webhook domain: {WEBHOOK_DOMAIN}")
    elif NGROK_AUTHTOKEN:
        ngrok.set_auth_token(NGROK_AUTHTOKEN)
        tunnel = ngrok.connect(8080, bind_tls=True)
        # Extract the public URL from the tunnel object
        public_url = tunnel.public_url
        webhook_url = f"{public_url}/webhooks"
        print(f"✓ Ngrok tunnel created: {public_url}")
    else:
        print("✗ Error: Either WEBHOOK_DOMAIN or NGROK_AUTHTOKEN must be set")
        sys.exit(1)

    # Create webhook
    try:
        webhook = agentmail.webhooks.create(
            url=webhook_url,
            event_types=["message.received"]
        )
        print(f"✓ Webhook configured: {webhook_url}")
        print(f"  Webhook ID: {webhook.webhook_id}")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"✓ Webhook already exists: {webhook_url}")
        else:
            print(f"✗ Error creating webhook: {e}")
            raise

    print("\n" + "=" * 60)
    print("Email Summary Agent Ready!")
    print("=" * 60)
    print(f"Inbox: {INBOX_USERNAME}@agentmail.to")
    print(f"Summary Recipient: {SUMMARY_RECIPIENT_EMAIL}")
    print(f"Daily Summary Time: {SUMMARY_TIME}")
    print(f"Webhook: {webhook_url}")
    print("\nHow it works:")
    print("  1. Receives emails in AgentMail inbox throughout the day")
    print("  2. At scheduled time, fetches all emails from inbox")
    print("  3. AI generates a summary and sends to your email")
    print("\nEndpoints:")
    print("  POST /summary/now - Send summary immediately")
    print("  GET /emails/today - View today's emails from inbox")
    print("  POST /load-samples - Send 12 sample emails to inbox")
    print("\nTo test: curl -X POST http://localhost:8080/load-samples")
    print("=" * 60 + "\n")


def main():
    """Main application entry point."""

    # Set up infrastructure
    setup_infrastructure()

    # Start summary scheduler in background thread
    scheduler_thread = threading.Thread(target=summary_scheduler, daemon=True)
    scheduler_thread.start()

    # Start Flask server
    print("Starting webhook server on port 8080...")
    app.run(host='0.0.0.0', port=8080, debug=False)


if __name__ == "__main__":
    main()
