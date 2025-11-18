"""
Sales Agent using AgentMail WebSocket

This is a simple example showing how to:
- Connect to AgentMail via WebSocket for real-time email processing
- Use OpenAI to handle sales conversations
- Send emails to prospects and respond to replies
"""

import asyncio
import os
import re
import json
import websockets
import websockets.exceptions
from dotenv import load_dotenv
from agentmail import AsyncAgentMail
from openai import AsyncOpenAI

# Load environment variables
load_dotenv()

# Initialize clients
agentmail = AsyncAgentMail(api_key=os.getenv("AGENTMAIL_API_KEY"))
openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Simple conversation history (thread_id -> messages)
conversations = {}

# Store manager email for notifications
manager_email = None


def extract_email(from_field):
    """Extract email address from 'Name <email@example.com>' format"""
    match = re.search(r'<(.+?)>', from_field)
    return match.group(1) if match else from_field


def is_from_manager(email_body):
    """Simple check if email is from sales manager (contains prospect info)"""
    keywords = ['prospect', 'lead', 'contact', 'reach out', 'email']
    return any(keyword in email_body.lower() for keyword in keywords)


def extract_prospect_info(email_body):
    """Extract prospect email from manager's message"""
    # Look for email addresses in the body
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, email_body)

    # Return the first email found (should be the prospect's email in the message body)
    if emails:
        return emails[0]
    return None


async def get_ai_response(messages, system_prompt):
    """Get response from OpenAI"""
    try:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                *messages
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error getting AI response: {e}")
        return "I apologize, but I encountered an error. Please try again."


async def send_email(inbox_id, to_email, subject, body):
    """Send a new email"""
    try:
        await agentmail.inboxes.messages.send(
            inbox_id=inbox_id,
            to=[to_email],
            subject=subject,
            text=body
        )
        print(f"✓ Sent email to {to_email}")
    except Exception as e:
        print(f"Error sending email: {e}")


async def reply_to_email(inbox_id, message_id, to_email, body):
    """Reply to an email"""
    try:
        await agentmail.inboxes.messages.reply(
            inbox_id=inbox_id,
            message_id=message_id,
            to=[to_email],  # Required parameter for replies
            text=body
        )
        print(f"✓ Sent reply to {to_email}")
    except Exception as e:
        print(f"Error replying: {e}")


async def handle_manager_email(inbox_id, message_id, from_email, subject, body):
    """Handle email from sales manager - extract prospect and send sales pitch"""
    global manager_email
    manager_email = from_email  # Remember manager for future notifications

    print(f"\n📧 Email from MANAGER: {from_email}")

    # Extract prospect email
    prospect_email = extract_prospect_info(body)
    print(f"→ Extracted prospect email: {prospect_email}")

    if not prospect_email:
        await reply_to_email(
            inbox_id,
            message_id,
            from_email,  # Reply back to the manager
            "I couldn't find a prospect email address. Please include it in your message."
        )
        return

    # Generate sales pitch using AI
    system_prompt = """You are a helpful sales agent. Generate a brief, professional sales email
    based on the manager's request. Keep it under 150 words. Be friendly and professional."""

    messages = [{"role": "user", "content": f"Create a sales email based on this: {body}"}]
    sales_pitch = await get_ai_response(messages, system_prompt)

    # Send email to prospect
    await send_email(
        inbox_id,
        prospect_email,
        f"Introduction: {subject}" if subject else "Quick Introduction",
        sales_pitch
    )

    # Confirm to manager
    await reply_to_email(
        inbox_id,
        message_id,
        from_email,  # Reply back to the manager
        f"✓ I've sent an introduction email to {prospect_email}.\n\nHere's what I sent:\n\n{sales_pitch}"
    )


async def handle_prospect_email(inbox_id, message_id, thread_id, from_email, subject, body):
    """Handle email from prospect - answer questions and notify manager"""
    print(f"\n📧 Email from PROSPECT: {from_email}")

    # Get conversation history
    if thread_id not in conversations:
        conversations[thread_id] = []

    conversations[thread_id].append({"role": "user", "content": body})

    # Determine intent
    intent_keywords = {
        'interested': ['interested', 'demo', 'meeting', 'tell me more', 'sounds good'],
        'not_interested': ['not interested', 'no thank', 'not right now', 'maybe later'],
        'question': ['?', 'how', 'what', 'when', 'why', 'can you']
    }

    body_lower = body.lower()
    intent = 'question'  # default

    for key, keywords in intent_keywords.items():
        if any(keyword in body_lower for keyword in keywords):
            intent = key
            break

    # Generate response
    system_prompt = """You are a helpful sales agent. Answer prospect questions professionally
    and helpfully. Keep responses brief (under 100 words). Be friendly but professional."""

    prospect_response = await get_ai_response(conversations[thread_id], system_prompt)

    # Reply to prospect
    await reply_to_email(inbox_id, message_id, from_email, prospect_response)

    # Notify manager if strong intent signal
    if manager_email and intent in ['interested', 'not_interested']:
        status = "showing interest" if intent == 'interested' else "not interested at this time"
        await send_email(
            inbox_id,
            manager_email,
            f"Update: {from_email}",
            f"Prospect {from_email} is {status}.\n\nTheir message:\n{body}\n\nMy response:\n{prospect_response}"
        )
        print(f"→ Notified manager about prospect's {intent}")

    # Update conversation
    conversations[thread_id].append({"role": "assistant", "content": prospect_response})


async def handle_new_email(message):
    """Process incoming email from WebSocket"""
    try:
        # Extract message data
        inbox_id = message.get("inbox_id")
        message_id = message.get("message_id")
        thread_id = message.get("thread_id")
        from_field = message.get("from_") or message.get("from", "")  # Check both from_ and from
        from_email = extract_email(from_field)
        subject = message.get("subject", "")
        body = message.get("text", "") or message.get("body", "")

        print(f"\n{'='*60}")
        print(f"New email from: {from_email}")
        print(f"Subject: {subject}")
        print(f"{'='*60}")

        # Determine if from manager or prospect
        if is_from_manager(body):
            await handle_manager_email(inbox_id, message_id, from_email, subject, body)
        else:
            await handle_prospect_email(inbox_id, message_id, thread_id, from_email, subject, body)

    except Exception as e:
        print(f"Error handling email: {e}")


async def main():
    """Main WebSocket loop"""
    inbox_username = os.getenv("INBOX_USERNAME", "sales-agent")
    websocket = None

    print(f"\n🚀 Sales Agent starting...")
    print(f"📬 Inbox: {inbox_username}@agentmail.to\n")

    # Create inbox (idempotent)
    try:
        inbox = await agentmail.inboxes.create(
            username=inbox_username,
            client_id=f"{inbox_username}-websocket-inbox"
        )
        inbox_id = inbox.inbox_id
        print(f"✓ Inbox ready: {inbox_id}")
    except Exception as e:
        if "already exists" in str(e).lower():
            inbox_id = f"{inbox_username}@agentmail.to"
            print(f"✓ Using existing inbox: {inbox_id}")
        else:
            print(f"Error creating inbox: {e}")
            return

    print(f"✓ Connecting to AgentMail WebSocket...")

    # Connect to WebSocket
    try:
        ws_url = "wss://ws.agentmail.to/v0"
        api_key = os.getenv("AGENTMAIL_API_KEY")

        websocket = await websockets.connect(
            ws_url,
            additional_headers={"Authorization": f"Bearer {api_key}"}
        )
        print(f"✓ Connected! Listening for emails...\n")

        # Subscribe to inbox
        subscribe_msg = {
            "type": "subscribe",
            "inbox_ids": [inbox_id]
        }
        await websocket.send(json.dumps(subscribe_msg))
        print(f"✓ Subscribed to {inbox_id}")

        # Listen for messages
        async for message_raw in websocket:
            event = json.loads(message_raw)

            # For events with type="event", use event_type field
            # For other events, use type field
            if event.get("type") == "event":
                event_type = event.get("event_type")
            else:
                event_type = event.get("type")

            # Debug: Log ALL events (comment out in production)
            # print(f"[DEBUG] Event received: type={event_type}")
            # print(f"[DEBUG] Full event: {json.dumps(event, indent=2)[:500]}...")

            # Log subscription confirmation
            if event_type == "subscribed":
                print(f"[Event: subscribed]\n")

            # Process message.received events
            if event_type == "message.received":
                print(f"📨 New email received!")
                await handle_new_email(event.get("message", {}))

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n\n👋 Shutting down gracefully...")
    except websockets.exceptions.ConnectionClosed:
        print("\n⚠️ WebSocket connection closed")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # Clean up WebSocket connection
        if websocket:
            await websocket.close()
            print("✓ WebSocket connection closed")


def run():
    """Run the main function with proper signal handling"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle KeyboardInterrupt at the top level
        print("\n✓ Shutdown complete")


if __name__ == "__main__":
    run()
