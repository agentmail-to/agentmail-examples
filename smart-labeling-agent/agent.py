"""
Smart Email Labeling Agent

An AI-powered email classification agent that automatically analyzes incoming
emails across multiple dimensions and applies appropriate labels for automated
inbox organization.
"""

import os
import json
import time
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, request, Response
import ngrok
from agentmail import AgentMail
from openai import OpenAI

# Configuration
PORT = int(os.getenv("PORT", "8080"))
INBOX_USERNAME = os.getenv("INBOX_USERNAME", "smart-labels")
WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN")

# Initialize
app = Flask(__name__)
client = AgentMail()
openai_client = OpenAI()


def setup_agentmail():
    """Create inbox and webhook with idempotency."""
    # Create inbox
    try:
        inbox = client.inboxes.create(
            username=INBOX_USERNAME,
            client_id=f"{INBOX_USERNAME}-inbox"
        )
    except Exception as e:
        if "already exists" in str(e).lower():
            inbox_id = f"{INBOX_USERNAME}@agentmail.to"
            class SimpleInbox:
                def __init__(self, inbox_id):
                    self.inbox_id = inbox_id
            inbox = SimpleInbox(inbox_id)
        else:
            raise

    # Start ngrok
    listener = ngrok.forward(PORT, domain=WEBHOOK_DOMAIN, authtoken_from_env=True)

    # Create webhook
    try:
        client.webhooks.create(
            url=f"{listener.url()}/webhook/agentmail",
            event_types=["message.received"],
            client_id=f"{INBOX_USERNAME}-webhook"
        )
    except Exception as e:
        if "already exists" not in str(e).lower():
            raise

    print(f" Ready: {inbox.inbox_id}\n")
    return inbox, listener


def analyze_email(subject, content):
    """Use AI to classify email across multiple dimensions with retry logic."""
    valid_values = {
        "sentiment": {"positive", "neutral", "negative"},
        "category": {"question", "complaint", "feature-request", "bug-report", "praise"},
        "priority": {"urgent", "high", "normal", "low"},
        "department": {"sales", "support", "billing", "technical"}
    }

    for attempt in range(1, 4):
        try:
            if attempt > 1:
                time.sleep(1)

            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert email classifier. Analyze emails and return structured classifications."
                    },
                    {
                        "role": "user",
                        "content": f"""Analyze this email across 4 dimensions:

                        Subject: {subject}
                        Content: {content}

                        Classify into:
                        1. sentiment: positive | neutral | negative
                        2. category: question | complaint | feature-request | bug-report | praise
                        3. priority: urgent | high | normal | low
                        4. department: sales | support | billing | technical

                        Consider:
                        - Sentiment: Overall tone and emotion
                        - Category: Primary intent of the email
                        - Priority: Urgency indicators (ASAP, urgent, immediately, deadline mentions, emergency)
                        - Department: Best team to handle this

                        Return ONLY valid JSON with these exact keys: sentiment, category, priority, department.
                        Example: {{"sentiment": "positive", "category": "question", "priority": "normal", "department": "sales"}}
                        """
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )

            # Parse and validate
            result = json.loads(response.choices[0].message.content)

            return result

        except Exception as e:
            if attempt == 3:
                raise Exception(f"AI classification failed: {e}")


def apply_labels(inbox_id, message_id, classifications):
    """Apply labels based on classification results."""
    labels = [
        f"{classifications['sentiment']}",
        f"{classifications['category']}",
        f"{classifications['priority']}",
        f"{classifications['department']}"
    ]

    # Try batch first
    try:
        client.inboxes.messages.update(
            inbox_id=inbox_id,
            message_id=message_id,
            add_labels=labels
        )
        for label in labels:
            print(f"  ✓ {label}")
        return
    except Exception:
        pass

    # Try individually
    successful = []
    for label in labels:
        try:
            client.inboxes.messages.update(
                inbox_id=inbox_id,
                message_id=message_id,
                add_labels=[label]
            )
            successful.append(label)
            print(f"  ✓ {label}")
        except Exception:
            print(f"  ✗ {label}")

    if not successful:
        raise Exception("Failed to apply labels")


@app.route('/webhook/agentmail', methods=['POST'])
def receive_webhook():
    """Webhook endpoint to receive incoming email notifications."""
    try:
        payload = request.json
        event_type = payload.get('type') or payload.get('event_type')

        # Ignore outgoing messages
        if event_type == 'message.sent':
            return Response(status=200)

        message = payload.get('message', {})
        message_id = message.get('message_id')
        inbox_id = message.get('inbox_id')
        from_field = message.get('from_', '') or message.get('from', '')

        # Validate required fields
        if not message_id or not inbox_id or not from_field:
            return Response(status=200)

        # Extract sender email
        if '<' in from_field and '>' in from_field:
            sender_email = from_field.split('<')[1].split('>')[0].strip()
        else:
            sender_email = from_field.strip()

        subject = message.get('subject', '(no subject)')
        email_body = message.get('text', '') or message.get('body', '') or message.get('html', '')

        # Log
        print(f"\n📧 {sender_email}: {subject}")

        # Analyze
        classifications = analyze_email(subject, email_body)

        print(f"  Sentiment: {classifications['sentiment']}")
        print(f"  Category: {classifications['category']}")
        print(f"  Priority: {classifications['priority']}")
        print(f"  Department: {classifications['department']}")

        # Apply labels
        apply_labels(inbox_id, message_id, classifications)
        print("Done\n")

    except Exception as e:
        print(f"Error: {e}\n")

    return Response(status=200)


if __name__ == '__main__':
    print("SMART EMAIL LABELING AGENT\n")
    inbox, listener = setup_agentmail()
    print("Waiting for emails...\n")
    app.run(port=PORT)
