import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const payload = await request.json();

  const { event, data } = payload;

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
