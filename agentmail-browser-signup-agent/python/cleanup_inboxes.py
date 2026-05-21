"""
One-shot helper to delete accumulated test inboxes when you hit the
"Inbox limit exceeded" error.

By default it deletes ALL inboxes in the account except the one named in
KEEP_INBOX_ID below. Edit KEEP_INBOX_ID if you want to preserve a
specific inbox; otherwise it deletes everything.

Run: python cleanup_inboxes.py
"""

import os

from agentmail import AgentMail
from dotenv import load_dotenv

load_dotenv()

# Set to a specific inbox_id you want to KEEP, or leave as None to delete all.
KEEP_INBOX_ID: str | None = None


def main() -> None:
    client = AgentMail(api_key=os.environ["AGENTMAIL_API_KEY"])

    inboxes = client.inboxes.list()
    items = inboxes.inboxes or []
    print(f"Found {len(items)} inbox(es) on this account:\n")
    for ib in items:
        marker = "  KEEP" if ib.inbox_id == KEEP_INBOX_ID else "DELETE"
        print(f"  [{marker}] {ib.email}  ({ib.display_name or '-'})")

    confirm = input("\nProceed with deletion? Type 'yes' to confirm: ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        return

    deleted = 0
    for ib in items:
        if ib.inbox_id == KEEP_INBOX_ID:
            continue
        try:
            client.inboxes.delete(ib.inbox_id)
            print(f"  ✓ deleted {ib.email}")
            deleted += 1
        except Exception as e:
            print(f"  ! failed to delete {ib.email}: {e}")

    print(f"\nDeleted {deleted} inbox(es).")


if __name__ == "__main__":
    main()
