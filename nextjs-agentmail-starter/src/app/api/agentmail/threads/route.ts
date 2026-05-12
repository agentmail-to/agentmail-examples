import { NextRequest, NextResponse } from "next/server";
import { AgentMailClient } from "agentmail";

const client = new AgentMailClient({
  apiKey: process.env.AGENTMAIL_API_KEY!,
});

export async function GET(request: NextRequest) {
  const inboxId = request.nextUrl.searchParams.get("inboxId");

  if (!inboxId) {
    return NextResponse.json(
      { error: "Missing required query param: inboxId" },
      { status: 400 }
    );
  }

  const threads = await client.inboxes.threads.list(inboxId);
  return NextResponse.json(threads);
}
