"""
Tiny helper to build an iCalendar (.ics) invite from scratch.

The .ics format is plain text — RFC 5545. Email clients (Gmail, Outlook, Apple
Mail) auto-detect text/calendar attachments and offer "Add to calendar" with
one click. No external service or OAuth required.
"""

import base64
from datetime import datetime, timedelta, timezone
from typing import Iterable
from uuid import uuid4

from agentmail.attachments.types.send_attachment import SendAttachment


def _ics_escape(text: str) -> str:
    """Escape iCal special chars (RFC 5545 §3.3.11)."""
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def build_ics(
    title: str,
    start_iso: str,
    duration_minutes: int,
    organizer_email: str,
    attendees: Iterable[str],
    description: str = "",
) -> str:
    """Build a VEVENT iCalendar string for a single meeting."""
    start = datetime.fromisoformat(start_iso)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    end = start + timedelta(minutes=duration_minutes)

    fmt = "%Y%m%dT%H%M%SZ"
    dtstart = start.astimezone(timezone.utc).strftime(fmt)
    dtend = end.astimezone(timezone.utc).strftime(fmt)
    dtstamp = datetime.now(timezone.utc).strftime(fmt)

    attendee_lines = [
        f"ATTENDEE;RSVP=TRUE;CN={a};ROLE=REQ-PARTICIPANT:mailto:{a}"
        for a in attendees
        if a
    ]

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AgentMail Scheduling Agent//EN",
        "METHOD:REQUEST",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{uuid4()}@agentmail-scheduling-agent",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{dtstart}",
        f"DTEND:{dtend}",
        f"SUMMARY:{_ics_escape(title)}",
        f"DESCRIPTION:{_ics_escape(description)}",
        f"ORGANIZER;CN={organizer_email}:mailto:{organizer_email}",
        *attendee_lines,
        "STATUS:CONFIRMED",
        "SEQUENCE:0",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    # iCal lines should be CRLF-separated.
    return "\r\n".join(lines) + "\r\n"


def ics_attachment(ics_text: str, filename: str = "invite.ics") -> SendAttachment:
    """Wrap an ICS string into an AgentMail SendAttachment."""
    encoded = base64.b64encode(ics_text.encode("utf-8")).decode("ascii")
    return SendAttachment(
        filename=filename,
        content_type="text/calendar; method=REQUEST; charset=UTF-8",
        content=encoded,
    )
