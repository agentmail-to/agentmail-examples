import { NextRequest, NextResponse } from "next/server";
import { AgentMailClient } from "agentmail";

const client = new AgentMailClient({
  apiKey: process.env.AGENTMAIL_API_KEY!,
});

export async function GET() {
  const inboxes = await client.inboxes.list();
  return NextResponse.json(inboxes);
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const inbox = await client.inboxes.create({
    displayName: body.displayName || "New Agent Inbox",
  });
  return NextResponse.json(inbox, { status: 201 });
}
