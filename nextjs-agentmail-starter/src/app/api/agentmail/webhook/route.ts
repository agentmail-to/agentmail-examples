import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  let payload: Record<string, unknown>;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const { event, data } = payload;

  if (typeof event !== "string" || !data || typeof data !== "object") {
    return NextResponse.json({ error: "Missing event or data" }, { status: 400 });
  }

  switch (event) {
    case "message.received":
      console.log(
        `New message in inbox ${data.inbox_id} from ${data.from_address}: ${data.subject}`
      );
      // Add your agent logic here:
      // - Classify the message
      // - Generate a response
      // - Send a reply
      break;

    case "message.sent":
      console.log(`Message sent from inbox ${data.inbox_id}: ${data.subject}`);
      break;

    default:
      console.log(`Unhandled event: ${event}`);
  }

  return NextResponse.json({ received: true });
}
