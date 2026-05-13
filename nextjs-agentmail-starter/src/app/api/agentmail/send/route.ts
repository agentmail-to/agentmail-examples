import { NextRequest, NextResponse } from "next/server";
import { AgentMailClient } from "agentmail";

const client = new AgentMailClient({
  apiKey: process.env.AGENTMAIL_API_KEY!,
});

export async function POST(request: NextRequest) {
  const body = await request.json();
  const { inboxId, to, subject, text } = body;

  if (!inboxId || !to || !subject || !text) {
    return NextResponse.json(
      { error: "Missing required fields: inboxId, to, subject, text" },
      { status: 400 }
    );
  }

  const message = await client.messages.send(inboxId, {
    to: Array.isArray(to) ? to : [to],
    subject,
    text,
  });

  return NextResponse.json(message, { status: 201 });
}
