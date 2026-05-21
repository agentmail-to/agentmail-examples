/**
 * Tiny helper to build an iCalendar (.ics) invite from scratch.
 * Same shape as the scheduling-agent helper.
 */

import { randomUUID } from "node:crypto";

function escapeIcs(text: string): string {
  return text
    .replace(/\\/g, "\\\\")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,")
    .replace(/\n/g, "\\n");
}

function toIcsUtc(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    date.getUTCFullYear().toString() +
    pad(date.getUTCMonth() + 1) +
    pad(date.getUTCDate()) +
    "T" +
    pad(date.getUTCHours()) +
    pad(date.getUTCMinutes()) +
    pad(date.getUTCSeconds()) +
    "Z"
  );
}

export function buildIcs(opts: {
  title: string;
  startIso: string;
  durationMinutes: number;
  organizerEmail: string;
  attendees: string[];
  description?: string;
}): string {
  const start = new Date(opts.startIso);
  const end = new Date(start.getTime() + opts.durationMinutes * 60_000);

  const attendeeLines = opts.attendees
    .filter(Boolean)
    .map(
      (a) =>
        `ATTENDEE;RSVP=TRUE;CN=${a};ROLE=REQ-PARTICIPANT:mailto:${a}`,
    );

  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//AgentMail Dinner Reservation Agent//EN",
    "METHOD:REQUEST",
    "CALSCALE:GREGORIAN",
    "BEGIN:VEVENT",
    `UID:${randomUUID()}@agentmail-dinner-reservation`,
    `DTSTAMP:${toIcsUtc(new Date())}`,
    `DTSTART:${toIcsUtc(start)}`,
    `DTEND:${toIcsUtc(end)}`,
    `SUMMARY:${escapeIcs(opts.title)}`,
    `DESCRIPTION:${escapeIcs(opts.description ?? "")}`,
    `ORGANIZER;CN=${opts.organizerEmail}:mailto:${opts.organizerEmail}`,
    ...attendeeLines,
    "STATUS:CONFIRMED",
    "SEQUENCE:0",
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  return lines.join("\r\n") + "\r\n";
}

export function icsAttachment(icsText: string, filename = "invite.ics") {
  return {
    filename,
    contentType: "text/calendar; method=REQUEST; charset=UTF-8",
    content: Buffer.from(icsText, "utf-8").toString("base64"),
  };
}
