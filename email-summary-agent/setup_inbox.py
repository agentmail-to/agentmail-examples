"""
Standalone script to create AgentMail inbox using the SDK.
"""

import os
import sys
from agentmail import AgentMail

# Configuration
AGENTMAIL_API_KEY = os.environ.get("AGENTMAIL_API_KEY")
INBOX_USERNAME = os.environ.get("INBOX_USERNAME", "summary-agent")

if not AGENTMAIL_API_KEY:
    print("Error: AGENTMAIL_API_KEY not set")
    sys.exit(1)

# Initialize AgentMail
agentmail = AgentMail(api_key=AGENTMAIL_API_KEY)

print(f"Creating inbox: {INBOX_USERNAME}@agentmail.to")

try:
    inbox = agentmail.inboxes.create(
        username=INBOX_USERNAME,
        domain="agentmail.to",
        display_name="Email Summary Agent"
    )
    print(f"✓ Success! Inbox created: {INBOX_USERNAME}@agentmail.to")
    print(f"  Inbox ID: {inbox.inbox_id}")
    print(f"  Display Name: {inbox.display_name}")

except Exception as e:
    if "already exists" in str(e).lower():
        print(f"✓ Inbox already exists: {INBOX_USERNAME}@agentmail.to")
    else:
        print(f"✗ Error: {e}")
        sys.exit(1)
