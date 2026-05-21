"""
EmailTools — wires AgentMail into Browser Use as agent tools.

Mirrors the official integration from browser-use/examples/integrations/agentmail/.
Adds two @action tools the LLM-driven browser agent can call:

  - get_email_address()        → returns the inbox address to use on signup forms
  - get_latest_email(max_age)  → polls / websocket-waits for the latest unread email

Use it by instantiating with an inbox and passing the instance to Agent(tools=...).
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

from agentmail import AsyncAgentMail, Message, MessageReceivedEvent, Subscribe
from agentmail.inboxes.types.inbox import Inbox
from agentmail.inboxes.types.inbox_id import InboxId
from browser_use import Tools

logger = logging.getLogger(__name__)


class EmailTools(Tools):
    """Browser Use Tools subclass that exposes inbox + email-fetching to the agent."""

    def __init__(
        self,
        email_client: AsyncAgentMail | None = None,
        email_timeout: int = 60,
        inbox: Inbox | None = None,
    ):
        super().__init__()
        self.email_client = email_client or AsyncAgentMail()
        self.email_timeout = email_timeout
        self.inbox: Inbox | None = inbox
        self._register_email_tools()

    # --- helpers --------------------------------------------------------------

    def _serialize_message_for_llm(self, message: Message) -> str:
        body = message.text
        if not body and message.html:
            body = self._html_to_text(message.html)
        return (
            f"From: {message.from_}\n"
            f"To: {message.to}\n"
            f"Timestamp: {message.timestamp.isoformat()}\n"
            f"Subject: {message.subject}\n"
            f"Body: {body}"
        )

    def _html_to_text(self, html: str) -> str:
        # Strip script/style blocks first
        html = re.sub(r"<script\b[^>]*>.*?</script\s*>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style\b[^>]*>.*?</style\s*>", "", html, flags=re.DOTALL | re.IGNORECASE)
        # Preserve link URLs: <a href="...">text</a> → text (https://...)
        # Critical for verification emails — without this, the agent sees the
        # button label but loses the actual verification URL.
        html = re.sub(
            r'<a\s+[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            lambda m: f"{m.group(2).strip()} ( {m.group(1)} )",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # Now strip remaining tags
        html = re.sub(r"<[^>]+>", " ", html)
        # Decode common entities
        for a, b in [
            ("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
            ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"),
        ]:
            html = html.replace(a, b)
        return re.sub(r"\s+", " ", html).strip()

    async def _get_or_create_inbox(self) -> Inbox:
        if self.inbox:
            return self.inbox
        self.inbox = await self.email_client.inboxes.create()
        return self.inbox

    async def _wait_for_message(self, inbox_id: InboxId) -> Message:
        """Open an AgentMail websocket and wait for the next received message."""
        async with self.email_client.websockets.connect() as ws:
            await ws.send_subscribe(message=Subscribe(inbox_ids=[inbox_id]))
            try:
                while True:
                    data = await asyncio.wait_for(ws.recv(), timeout=self.email_timeout)
                    if isinstance(data, MessageReceivedEvent):
                        await self.email_client.inboxes.messages.update(
                            inbox_id=inbox_id,
                            message_id=data.message.message_id,
                            remove_labels=["unread"],
                        )
                        return data.message
            except TimeoutError:
                raise TimeoutError(
                    f"No email received in the inbox in {self.email_timeout}s"
                )

    # --- registered tools (visible to the agent) ------------------------------

    def _register_email_tools(self):
        @self.action(
            "Get the email address to use on signup forms. "
            "Pass this to any 'Email' input field on the page. "
            "This is the ONLY way to learn the inbox address — never invent or guess one."
        )
        async def get_email_address() -> str:
            inbox = await self._get_or_create_inbox()
            return inbox.inbox_id

        @self.action(
            "READ THE LATEST EMAIL from the agent's own inbox. Returns the subject + body as a string. "
            "Use this AFTER submitting a signup or login form, whenever the page tells you to "
            "'check your email' / 'enter the code we sent' / 'click the verification link'. "
            "Polls + waits up to email_timeout seconds for new mail to arrive. "
            "DO NOT navigate the browser to any inbox URL — there is no public web inbox to visit. "
            "DO NOT try to open AgentMail, Gmail, or any other webmail UI. "
            "This tool is the only correct way to read the agent's email."
        )
        async def get_latest_email(max_age_minutes: int = 5) -> str:
            inbox = await self._get_or_create_inbox()

            # List ALL recent received messages (not just unread) so the agent can
            # re-fetch the same verification email on a second call if it missed
            # extracting the URL on the first pass. We filter by the `received`
            # label so we don't surface our own outgoing mail.
            emails = await self.email_client.inboxes.messages.list(
                inbox_id=inbox.inbox_id, labels=["received"]
            )
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
            recent: list[Message] = []
            for stub in (emails.messages or []):
                full = await self.email_client.inboxes.messages.get(
                    inbox_id=inbox.inbox_id, message_id=stub.message_id
                )
                ts = full.timestamp if full.timestamp.tzinfo else full.timestamp.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    recent.append(full)

            if recent:
                recent.sort(key=lambda m: m.timestamp, reverse=True)
                latest = recent[0]
                # Note: we deliberately do NOT mark the message as read here, so a
                # second call can return the same message if the first call's
                # extraction missed something.
                return self._serialize_message_for_llm(latest)

            # Otherwise, websocket-wait for the next one
            try:
                msg = await self._wait_for_message(inbox_id=inbox.inbox_id)
                return self._serialize_message_for_llm(msg)
            except TimeoutError:
                return f"No email received in the inbox in {self.email_timeout}s"
