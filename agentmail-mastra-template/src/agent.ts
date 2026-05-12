import { Agent } from "@mastra/core/agent";
import { openai } from "@ai-sdk/openai";
import { createInbox, sendEmail, listMessages, replyToMessage } from "./tools/agentmail.js";

export const emailAgent = new Agent({
  name: "Email Agent",
  instructions: `You are an AI agent with email capabilities. You can create inboxes, send emails, check for new messages, and reply to conversations.

When asked to do something involving email:
1. If no inbox exists yet, create one first
2. Use the appropriate tool for the task
3. Report what you did clearly

Be proactive about checking for new messages when the user asks about their inbox.`,
  model: openai("gpt-4o-mini"),
  tools: {
    createInbox,
    sendEmail,
    listMessages,
    replyToMessage,
  },
});
