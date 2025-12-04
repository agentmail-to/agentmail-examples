"""
Dinner Agent using AgentMail Webhook

A simple example showing how to:
- Organize group dinners via email
- Collect RSVPs and track confirmations
- Automatically "book" a restaurant when threshold is met
- Send confirmation emails to all participants

This demonstrates multi-step workflow, state management, and threshold-based actions.
"""

import os
import re
import random
import uuid
from datetime import datetime
from threading import Thread
from flask import Flask, request, Response, jsonify
from dotenv import load_dotenv
import ngrok
from agentmail import AgentMail

# Load environment variables
load_dotenv()

# Flask app
app = Flask(__name__)

# AgentMail client
client = AgentMail(api_key=os.getenv("AGENTMAIL_API_KEY"))

# Configuration
INBOX_USERNAME = os.getenv("INBOX_USERNAME", "dinner-agent")
NGROK_DOMAIN = os.getenv("NGROK_DOMAIN") or os.getenv("WEBHOOK_DOMAIN")
MIN_CONFIRMATIONS = int(os.getenv("MIN_CONFIRMATIONS", "3"))
PORT = int(os.getenv("PORT", "8080"))

# In-memory storage for dinner events
dinner_events = {}  # event_id -> event_data

# Global inbox info (set during setup)
inbox_id = None
inbox_email = None


# =============================================================================
# MOCK DATA - Restaurant options
# =============================================================================

RESTAURANTS = [
    {
        "name": "Thai Garden",
        "cuisine": "Thai",
        "address": "123 Main St, San Francisco",
        "phone": "(555) 123-4567"
    },
    {
        "name": "Golden Dragon",
        "cuisine": "Chinese",
        "address": "456 Oak Ave, San Francisco",
        "phone": "(555) 234-5678"
    },
    {
        "name": "Curry House",
        "cuisine": "Indian",
        "address": "789 Pine Rd, San Francisco",
        "phone": "(555) 345-6789"
    },
    {
        "name": "Sakura Sushi",
        "cuisine": "Japanese",
        "address": "321 Cherry Ln, San Francisco",
        "phone": "(555) 456-7890"
    },
]


# =============================================================================
# CLASSIFICATION KEYWORDS
# =============================================================================

REQUEST_KEYWORDS = [
    'organize dinner', 'plan dinner', 'group dinner', 'team dinner',
    'dinner for', 'book restaurant', 'make reservation', 'schedule dinner'
]

RSVP_KEYWORDS = [
    'count me in', 'i can make it', "i'll be there", 'yes, i can attend',
    "i'm in", 'i can come', 'confirmed', 'i will attend', 'sign me up'
]


# =============================================================================
# HELPER FUNCTIONS - Extraction
# =============================================================================

def extract_email(from_field):
    """Extract email address from 'Name <email@example.com>' format"""
    match = re.search(r'<(.+?)>', from_field)
    return match.group(1) if match else from_field


def extract_name_from_email(email):
    """Extract name from email address (before @)"""
    return email.split('@')[0].replace('.', ' ').replace('_', ' ').title()


def extract_participant_name(body, from_email):
    """Extract participant name from email body or fallback to email"""
    # Try common signature patterns
    patterns = [
        r'[-–]\s*([A-Za-z\s]+)$',           # "- John" at end
        r'thanks,\s*([A-Za-z\s]+)',          # "Thanks, John"
        r'regards,\s*([A-Za-z\s]+)',         # "Regards, John"
        r'best,\s*([A-Za-z\s]+)',            # "Best, John"
        r'cheers,\s*([A-Za-z\s]+)',          # "Cheers, John"
    ]

    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE | re.MULTILINE)
        if match:
            name = match.group(1).strip()
            if len(name) > 1 and len(name) < 50:
                return name

    # Fallback to email-based name
    return extract_name_from_email(from_email)


def extract_dinner_details(body):
    """Extract party size, day, and time from email body"""
    details = {
        'party_size': None,
        'day': None,
        'time': None
    }

    body_lower = body.lower()

    # Extract party size
    party_patterns = [
        r'dinner for (\d+)',
        r'(\d+)\s*people',
        r'party of (\d+)',
        r'group of (\d+)',
        r'(\d+)\s*guests',
    ]
    for pattern in party_patterns:
        match = re.search(pattern, body_lower)
        if match:
            details['party_size'] = int(match.group(1))
            break

    # Extract day
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    for day in days:
        if day in body_lower:
            details['day'] = day.capitalize()
            break

    # Extract time
    time_pattern = r'(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM))'
    match = re.search(time_pattern, body)
    if match:
        details['time'] = match.group(1)

    return details


# =============================================================================
# HELPER FUNCTIONS - Classification
# =============================================================================

def is_dinner_request(subject, body):
    """Check if email is a new dinner organization request"""
    combined = f"{subject} {body}".lower()
    return any(keyword in combined for keyword in REQUEST_KEYWORDS)


def is_rsvp(subject, body):
    """Check if email is an RSVP confirmation"""
    combined = f"{subject} {body}".lower()
    return any(keyword in combined for keyword in RSVP_KEYWORDS)


# =============================================================================
# HELPER FUNCTIONS - State Management
# =============================================================================

def create_event(organizer_email, organizer_name, details):
    """Create a new dinner event and return its ID"""
    event_id = f"dinner_{uuid.uuid4().hex[:8]}"

    dinner_events[event_id] = {
        'id': event_id,
        'state': 'collecting',  # collecting | ready | booked
        'organizer': {
            'name': organizer_name,
            'email': organizer_email
        },
        'participants': [],  # List of {name, email, confirmed_at}
        'party_size': details.get('party_size') or MIN_CONFIRMATIONS,
        'day': details.get('day') or 'Saturday',
        'time': details.get('time') or '7:00 PM',
        'min_confirmations': MIN_CONFIRMATIONS,
        'restaurant': None,
        'confirmation_number': None,
        'created_at': datetime.now().isoformat()
    }

    return event_id


def find_active_event():
    """Find the most recent active (non-booked) event"""
    for event_id, event in sorted(dinner_events.items(),
                                   key=lambda x: x[1]['created_at'],
                                   reverse=True):
        if event['state'] != 'booked':
            return event_id
    return None


def is_already_confirmed(event_id, email):
    """Check if participant already confirmed for this event"""
    event = dinner_events.get(event_id)
    if not event:
        return False

    # Check if organizer
    if event['organizer']['email'].lower() == email.lower():
        return True

    # Check participants
    return any(p['email'].lower() == email.lower() for p in event['participants'])


def add_participant(event_id, email, name):
    """Add a participant to the event"""
    event = dinner_events.get(event_id)
    if not event:
        return False

    event['participants'].append({
        'name': name,
        'email': email,
        'confirmed_at': datetime.now().isoformat()
    })
    return True


def get_confirmed_count(event_id):
    """Get total confirmed count (organizer + participants)"""
    event = dinner_events.get(event_id)
    if not event:
        return 0
    return 1 + len(event['participants'])  # 1 for organizer


def is_ready_to_book(event_id):
    """Check if event has enough confirmations to book"""
    event = dinner_events.get(event_id)
    if not event:
        return False
    return (event['state'] == 'collecting' and
            get_confirmed_count(event_id) >= event['min_confirmations'])


def get_all_participant_emails(event_id):
    """Get all participant emails including organizer"""
    event = dinner_events.get(event_id)
    if not event:
        return []

    emails = [event['organizer']['email']]
    emails.extend(p['email'] for p in event['participants'])
    return emails


def get_participant_list(event_id):
    """Get formatted list of all participants"""
    event = dinner_events.get(event_id)
    if not event:
        return ""

    names = [f"• {event['organizer']['name']} (organizer)"]
    names.extend(f"• {p['name']}" for p in event['participants'])
    return '\n'.join(names)


# =============================================================================
# HELPER FUNCTIONS - Booking
# =============================================================================

def select_restaurant():
    """Select a random restaurant"""
    return random.choice(RESTAURANTS)


def generate_confirmation_number():
    """Generate a fake confirmation number"""
    return f"DIN-{uuid.uuid4().hex[:8].upper()}"


# =============================================================================
# CORE HANDLERS
# =============================================================================

def handle_dinner_request(message_id, from_email, subject, body):
    """
    Handle new dinner organization request.
    Creates event and sends confirmation to organizer.
    """
    print(f"\n[INFO] New dinner request from {from_email}")

    # Extract details from email
    details = extract_dinner_details(body)
    organizer_name = extract_participant_name(body, from_email)

    print(f"[DEBUG] Extracted: party_size={details['party_size']}, day={details['day']}, time={details['time']}")

    # Create event
    event_id = create_event(from_email, organizer_name, details)
    event = dinner_events[event_id]

    print(f"[SUCCESS] ✓ Event {event_id} created")
    print(f"[DEBUG] State: collecting, RSVPs: 1/{event['min_confirmations']}")

    # Send confirmation to organizer
    response_text = f"""Thanks for organizing dinner! 🍽️

Event Details:
• Party size: {event['party_size']} people
• Preferred day: {event['day']}
• Preferred time: {event['time']}

I'll wait for {event['min_confirmations']} people to confirm before booking a restaurant.
Have your guests email me at {inbox_email} to RSVP!

Current RSVPs: 1/{event['min_confirmations']} (you're counted as the organizer!)

- Dinner Agent"""

    try:
        client.inboxes.messages.reply(
            inbox_id=inbox_id,
            message_id=message_id,
            to=[from_email],
            text=response_text
        )
        print(f"[SUCCESS] ✓ Confirmation sent to organizer")
    except Exception as e:
        print(f"[ERROR] Failed to send confirmation: {e}")


def handle_rsvp(message_id, from_email, subject, body):
    """
    Handle RSVP confirmation.
    Adds participant and checks if ready to book.
    """
    print(f"\n[INFO] RSVP received from {from_email}")

    # Find active event
    event_id = find_active_event()
    if not event_id:
        print(f"[WARN] No active event found for {from_email}")
        try:
            client.inboxes.messages.reply(
                inbox_id=inbox_id,
                message_id=message_id,
                to=[from_email],
                text="""I couldn't find an active dinner event for your RSVP.

Please ask the organizer to send me a dinner request first, then try RSVPing again.

- Dinner Agent"""
            )
        except Exception as e:
            print(f"[ERROR] Failed to send error response: {e}")
        return

    event = dinner_events[event_id]

    # Check for duplicate RSVP
    if is_already_confirmed(event_id, from_email):
        print(f"[WARN] Duplicate RSVP from {from_email}")
        count = get_confirmed_count(event_id)
        try:
            client.inboxes.messages.reply(
                inbox_id=inbox_id,
                message_id=message_id,
                to=[from_email],
                text=f"""You've already confirmed for this dinner!

Current RSVPs: {count}/{event['min_confirmations']}

- Dinner Agent"""
            )
        except Exception as e:
            print(f"[ERROR] Failed to send duplicate response: {e}")
        return

    # Add participant
    participant_name = extract_participant_name(body, from_email)
    add_participant(event_id, from_email, participant_name)
    print(f"[SUCCESS] ✓ Participant {participant_name} added")

    count = get_confirmed_count(event_id)
    remaining = event['min_confirmations'] - count
    print(f"[DEBUG] Current RSVPs: {count}/{event['min_confirmations']}")

    # Check if ready to book
    if is_ready_to_book(event_id):
        print(f"[SUCCESS] ✓ Threshold reached! Booking restaurant...")

        # Send immediate response
        try:
            client.inboxes.messages.reply(
                inbox_id=inbox_id,
                message_id=message_id,
                to=[from_email],
                text=f"""Thanks for confirming, {participant_name}! 🎉

You're confirmed for the group dinner.
Current RSVPs: {count}/{event['min_confirmations']}

🎊 Great news! We have enough people - booking a restaurant now!

- Dinner Agent"""
            )
        except Exception as e:
            print(f"[ERROR] Failed to send RSVP response: {e}")

        # Trigger booking in background
        Thread(target=book_and_notify, args=(event_id,), daemon=True).start()

    else:
        # Send waiting response
        try:
            client.inboxes.messages.reply(
                inbox_id=inbox_id,
                message_id=message_id,
                to=[from_email],
                text=f"""Thanks for confirming, {participant_name}! 🎉

You're confirmed for the group dinner.
Current RSVPs: {count}/{event['min_confirmations']}

Waiting for {remaining} more confirmation(s) before I can book.

- Dinner Agent"""
            )
            print(f"[SUCCESS] ✓ RSVP confirmation sent")
        except Exception as e:
            print(f"[ERROR] Failed to send RSVP response: {e}")


def book_and_notify(event_id):
    """
    Book restaurant and notify all participants.
    Runs in background thread after threshold is met.
    """
    print(f"\n[INFO] Starting booking process for {event_id}")

    event = dinner_events.get(event_id)
    if not event:
        print(f"[ERROR] Event {event_id} not found")
        return

    # Update state
    event['state'] = 'ready'

    # Select restaurant and generate confirmation
    restaurant = select_restaurant()
    confirmation_number = generate_confirmation_number()

    # Update event
    event['restaurant'] = restaurant
    event['confirmation_number'] = confirmation_number
    event['state'] = 'booked'

    print(f"[SUCCESS] ✓ Booking complete - {restaurant['name']}")
    print(f"[DEBUG] Confirmation #: {confirmation_number}")

    # Build confirmation message
    participant_list = get_participant_list(event_id)
    count = get_confirmed_count(event_id)

    confirmation_text = f"""🎉 Your dinner is confirmed!

Restaurant: {restaurant['name']} ({restaurant['cuisine']} cuisine)
Address: {restaurant['address']}
Phone: {restaurant['phone']}
Date: {event['day']}
Time: {event['time']}
Party Size: {count} people
Confirmation #: {confirmation_number}

Attendees:
{participant_list}

See you there! 🍽️
- Dinner Agent"""

    # Send to all participants
    all_emails = get_all_participant_emails(event_id)
    success_count = 0

    for email in all_emails:
        try:
            client.inboxes.messages.send(
                inbox_id=inbox_id,
                to=[email],
                subject=f"🎉 Dinner Confirmed - {restaurant['name']}",
                text=confirmation_text
            )
            success_count += 1
        except Exception as e:
            print(f"[ERROR] Failed to send confirmation to {email}: {e}")

    print(f"[SUCCESS] ✓ Confirmations sent to {success_count}/{len(all_emails)} participants")


def process_email(payload):
    """
    Main email router.
    Classifies email and routes to appropriate handler.
    """
    try:
        message = payload.get('message', {})
        message_id = message.get('message_id')
        from_field = message.get('from', '')
        from_email = extract_email(from_field)
        subject = message.get('subject', '')
        body = message.get('text', '') or message.get('body', '')

        print(f"\n{'='*60}")
        print(f"[INFO] New email from: {from_email}")
        print(f"[INFO] Subject: {subject}")
        print(f"{'='*60}")

        # Classify and route
        if is_dinner_request(subject, body):
            handle_dinner_request(message_id, from_email, subject, body)
        elif is_rsvp(subject, body):
            handle_rsvp(message_id, from_email, subject, body)
        else:
            print(f"[WARN] Email not recognized as dinner request or RSVP")
            # Optional: send a help message
            try:
                client.inboxes.messages.reply(
                    inbox_id=inbox_id,
                    message_id=message_id,
                    to=[from_email],
                    text="""Hi! I'm the Dinner Agent. I can help you organize group dinners.

To organize a dinner, send me an email like:
"Please organize dinner for 6 people on Saturday at 7pm"

To RSVP for an existing dinner, reply with:
"Count me in!" or "I can make it!"

- Dinner Agent"""
                )
            except Exception as e:
                print(f"[ERROR] Failed to send help message: {e}")

    except Exception as e:
        print(f"[ERROR] Error processing email: {e}")


# =============================================================================
# FLASK ROUTES
# =============================================================================

@app.route("/webhook", methods=["POST"])
def receive_webhook():
    """Receive webhook from AgentMail and process in background"""
    payload = request.json
    # Process in background thread to avoid blocking
    Thread(target=process_email, args=(payload,), daemon=True).start()
    return Response(status=200)


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "agent": "dinner-agent"})


@app.route("/status", methods=["GET"])
def status():
    """Show current events status (for debugging)"""
    events_summary = []
    for event_id, event in dinner_events.items():
        events_summary.append({
            "id": event_id,
            "state": event["state"],
            "organizer": event["organizer"]["email"],
            "confirmed": get_confirmed_count(event_id),
            "min_required": event["min_confirmations"],
            "restaurant": event["restaurant"]["name"] if event["restaurant"] else None,
            "created_at": event["created_at"]
        })
    return jsonify({
        "active_events": len([e for e in dinner_events.values() if e["state"] != "booked"]),
        "total_events": len(dinner_events),
        "events": events_summary
    })


# =============================================================================
# INFRASTRUCTURE SETUP
# =============================================================================

def setup_infrastructure():
    """Create inbox and register webhook with ngrok tunnel"""
    global inbox_id, inbox_email

    print(f"\n[INFO] Setting up infrastructure...")

    # Create inbox
    inbox_client_id = f"{INBOX_USERNAME}-webhook-inbox"
    try:
        inbox = client.inboxes.create(
            username=INBOX_USERNAME,
            client_id=inbox_client_id
        )
        inbox_id = inbox.inbox_id
        inbox_email = f"{INBOX_USERNAME}@agentmail.to"
        print(f"[SUCCESS] ✓ Inbox created: {inbox_email}")
    except Exception as e:
        if "already exists" in str(e).lower():
            inbox_id = f"{INBOX_USERNAME}@agentmail.to"
            inbox_email = inbox_id
            print(f"[INFO] Using existing inbox: {inbox_email}")
        else:
            print(f"[ERROR] Failed to create inbox: {e}")
            raise

    # Setup ngrok tunnel
    if not NGROK_DOMAIN:
        print(f"[ERROR] NGROK_DOMAIN not set in environment")
        raise ValueError("NGROK_DOMAIN is required")

    print(f"[INFO] Creating ngrok tunnel...")
    listener = ngrok.forward(PORT, domain=NGROK_DOMAIN, authtoken_from_env=True)
    webhook_url = f"{listener.url()}/webhook"
    print(f"[SUCCESS] ✓ Ngrok tunnel: {listener.url()}")

    # Register webhook
    webhook_client_id = f"{INBOX_USERNAME}-webhook"
    try:
        client.webhooks.create(
            url=webhook_url,
            client_id=webhook_client_id,
            event_types=["message.received"],
            inbox_ids=[inbox_id]
        )
        print(f"[SUCCESS] ✓ Webhook registered: {webhook_url}")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"[INFO] Using existing webhook")
        else:
            print(f"[ERROR] Failed to register webhook: {e}")
            raise

    print(f"\n{'='*60}")
    print(f"🍽️  Dinner Agent Ready!")
    print(f"📧 Email: {inbox_email}")
    print(f"🔗 Webhook: {webhook_url}")
    print(f"👥 Min confirmations: {MIN_CONFIRMATIONS}")
    print(f"{'='*60}\n")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    print("🍽️  Dinner Agent starting...")
    print(f"[INFO] Configuration:")
    print(f"  • Username: {INBOX_USERNAME}")
    print(f"  • Min confirmations: {MIN_CONFIRMATIONS}")
    print(f"  • Port: {PORT}")

    setup_infrastructure()
    app.run(host="0.0.0.0", port=PORT)