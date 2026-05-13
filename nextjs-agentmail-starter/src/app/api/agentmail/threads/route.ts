import { NextRequest, NextResponse } from "next/server";
import { AgentMailClient } from "agentmail";

const client = new AgentMailClient({
  apiKey: process.env.AGENTMAIL_API_KEY!,
});

// TODO: Add authentication before deploying to production.
// Example: validate a session token, API key header, or JWT.
export async function GET(request: NextRequest) {
  const authHeader = request.headers.get("authorization");
  if (process.env.API_SECRET && authHeader !== `Bearer ${process.env.API_SECRET}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

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
