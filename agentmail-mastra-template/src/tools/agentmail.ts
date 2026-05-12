import { createTool } from "@mastra/core/tools";
import { z } from "zod";
import { AgentMailClient } from "agentmail";

const client = new AgentMailClient({
  apiKey: process.env.AGENTMAIL_API_KEY!,
});

export const createInbox = createTool({
  id: "create-inbox",
  description: "Create a new email inbox for the agent. Returns the inbox ID and email address.",
  inputSchema: z.object({
    displayName: z.string().describe("Display name for the inbox"),
  }),
  execute: async ({ context }) => {
    const inbox = await client.inboxes.create({
      displayName: context.displayName,
    });
    return { inboxId: inbox.id, email: inbox.email };
  },
});

export const sendEmail = createTool({
  id: "send-email",
  description: "Send an email from an agent inbox.",
  inputSchema: z.object({
    inboxId: z.string().describe("The inbox ID to send from"),
    to: z.string().describe("Recipient email address"),
    subject: z.string().describe("Email subject"),
    text: z.string().describe("Email body text"),
  }),
  execute: async ({ context }) => {
    const message = await client.messages.send(context.inboxId, {
      to: [context.to],
      subject: context.subject,
      text: context.text,
    });
    return { messageId: message.id, status: "sent" };
  },
});

export const listMessages = createTool({
  id: "list-messages",
  description: "List messages in an inbox. Optionally filter by labels.",
  inputSchema: z.object({
    inboxId: z.string().describe("The inbox ID to check"),
    labels: z.array(z.string()).optional().describe("Filter by labels, e.g. ['unread']"),
  }),
  execute: async ({ context }) => {
    const messages = await client.messages.list(context.inboxId, {
      labels: context.labels,
    });
    return {
      count: messages.data.length,
      messages: messages.data.map((m: any) => ({
        id: m.id,
        from: m.from_address,
        subject: m.subject,
        text: m.text?.substring(0, 500),
        labels: m.labels,
      })),
    };
  },
});

export const replyToMessage = createTool({
  id: "reply-to-message",
  description: "Reply to a specific message in an inbox.",
  inputSchema: z.object({
    inboxId: z.string().describe("The inbox ID"),
    messageId: z.string().describe("The message ID to reply to"),
    text: z.string().describe("Reply body text"),
  }),
  execute: async ({ context }) => {
    const reply = await client.messages.reply(context.inboxId, context.messageId, {
      text: context.text,
    });
    return { messageId: reply.id, status: "replied" };
  },
});
