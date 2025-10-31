"""
Auto-Reply Email Agent

A simple example showing how to build an email auto-reply bot with AgentMail.
This agent automatically responds to incoming emails with personalized messages.
"""

import os
from dotenv import load_dotenv

# Load environment variables before importing AgentMail
load_dotenv()

from flask import Flask, request, Response
import ngrok
from agentmail import AgentMail
from openai import OpenAI

# Configuration
PORT = 8080
INBOX_USERNAME = os.getenv("INBOX_USERNAME", "auto-reply")
WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN")
USE_AI_REPLY = os.getenv("USE_AI_REPLY", "false").lower() == "true"

# Initialize Flask app and AgentMail client
app = Flask(__name__)
client = AgentMail()
openai_client = OpenAI() if USE_AI_REPLY else None


def setup_agentmail():
    """Create inbox and webhook with idempotency."""
    print("Setting up AgentMail infrastructure...")

    # Create inbox (or get existing one)
    try:
        inbox = client.inboxes.create(
            username=INBOX_USERNAME,
            client_id=f"{INBOX_USERNAME}-inbox"
        )
        print(f"✓ Inbox created: {inbox.inbox_id}")
    except Exception as e:
        if "already exists" in str(e).lower():
            inbox_id = f"{INBOX_USERNAME}@agentmail.to"
            class SimpleInbox:
                def __init__(self, inbox_id):
                    self.inbox_id = inbox_id
            inbox = SimpleInbox(inbox_id)
            print(f"✓ Using existing inbox: {inbox.inbox_id}")
        else:
            raise

    # Start ngrok tunnel
    listener = ngrok.forward(PORT, domain=WEBHOOK_DOMAIN, authtoken_from_env=True)

    # Create webhook (or get existing one)
    try:
        webhook = client.webhooks.create(
            url=f"{listener.url()}/webhook/agentmail",
            event_types=["message.received"],
            client_id=f"{INBOX_USERNAME}-webhook"
        )
        print(f"✓ Webhook created")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"Webhook already exists")
        else:
            raise

    print(f"\n✓ Setup complete!")
    print(f"  Inbox: {inbox.inbox_id}")
    print(f"  Webhook: {listener.url()}/webhook/agentmail\n")

    return inbox, listener


def generate_reply(sender_name, subject):
    """Generate auto-reply message using a template."""
    return (
        f"Hi {sender_name},\n\n"
        f"Thank you for your email! I've received your message and will get back to you within 24 hours.\n\n"
        f"If your matter is urgent, please reply with \"URGENT\" in the subject line.\n\n"
        f"Best regards,\n"
        f"Auto-Reply Agent"
    )


def get_thread_history(thread_id):
    """Fetch conversation history for the thread."""
    try:
        thread = client.threads.get(thread_id=thread_id)
        # thread.get() returns a Thread object with messages
        return thread.messages if hasattr(thread, 'messages') else []
    except Exception as e:
        print(f"Failed to fetch thread history: {e}")
        return []


def format_thread_for_ai(messages):
    """Format thread messages into conversation history for AI."""
    conversation = []

    for msg in messages:
        # Handle both dict and object formats
        if hasattr(msg, 'from_'):
            sender = msg.from_
            text = msg.text or msg.html or ""
        else:
            sender = msg.get('from_', '') or msg.get('from', '')
            text = msg.get('text', '') or msg.get('html', '') or msg.get('body', '')

        # Extract just the email from "Name <email>" format
        if '<' in sender and '>' in sender:
            sender = sender.split('<')[1].split('>')[0].strip()

        if text:
            conversation.append(f"From: {sender}\n{text}")

    return "\n\n---\n\n".join(reversed(conversation))  # Reverse to show oldest first


def generate_ai_reply(sender_name, email_body, subject, thread_history=""):
    """Generate AI-powered reply using OpenAI with thread context."""
    try:
        # Build context message
        context = f"Email thread history:\n\n{thread_history}\n\n---\n\nLatest message from {sender_name}:\nSubject: {subject}\n{email_body}" if thread_history else f"Subject: {subject}\nFrom: {sender_name}\n{email_body}"

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an intelligent email assistant. Read the email thread and respond in a helpful, contextual way. If this is a follow-up in a conversation, acknowledge what was previously discussed. If you can provide helpful information based on the context, do so. If the question requires detailed research or expertise you don't have, acknowledge receipt and set expectations. Be conversational, professional, and concise."
                },
                {
                    "role": "user",
                    "content": f"{context}\n\nGenerate a helpful reply that considers the conversation history. Keep it concise (2-4 sentences) but be actually helpful if you can address their question or continue the conversation meaningfully."
                }
            ],
            max_tokens=250,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI generation failed, using template: {e}")
        return generate_reply(sender_name, subject)


@app.route('/webhook/agentmail', methods=['POST'])
def receive_webhook():
    """Webhook endpoint to receive incoming email notifications."""
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

    # Extract sender email and name
    if '<' in from_field and '>' in from_field:
        sender_email = from_field.split('<')[1].split('>')[0].strip()
        sender_name = from_field.split('<')[0].strip()
        if not sender_name or ',' in sender_name:
            sender_name = sender_email.split('@')[0].title()
    else:
        sender_email = from_field.strip()
        sender_name = sender_email.split('@')[0].title() if '@' in sender_email else 'Friend'

    subject = message.get('subject', '(no subject)')
    thread_id = message.get('thread_id', '')

    # Log incoming email
    print(f"Email from {sender_email}: {subject}")

    # Generate and send auto-reply
    try:
        if USE_AI_REPLY:
            email_body = message.get('text', '') or message.get('body', '')

            # Fetch thread history for context
            thread_history = ""
            if thread_id:
                print(f"Fetching thread history for: {thread_id[:20]}...")
                messages = get_thread_history(thread_id)
                if messages:
                    thread_history = format_thread_for_ai(messages)
                    print(f"Found {len(messages)} messages in thread")

            reply_text = generate_ai_reply(sender_name, email_body, subject, thread_history)
            print("Using AI-generated reply with thread context")
        else:
            reply_text = generate_reply(sender_name, subject)
            print("Using template reply")

        client.inboxes.messages.reply(
            inbox_id=inbox_id,
            message_id=message_id,
            to=[sender_email],
            text=reply_text
        )
        print(f"Auto-reply sent to {sender_email}\n")
    except Exception as e:
        print(f"Error: {e}\n")

    return Response(status=200)


if __name__ == '__main__':
    print("\n" + "="*60)
    print("AUTO-REPLY EMAIL AGENT")
    print("="*60 + "\n")

    inbox, listener = setup_agentmail()

    print(f"Agent is ready!")
    print(f"Send emails to: {inbox.inbox_id}")
    print(f"Reply mode: {'AI-powered' if USE_AI_REPLY else 'Template-based'}")
    print(f"\nWaiting for incoming emails...\n")

    app.run(port=PORT)
