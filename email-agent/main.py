import os
import asyncio
from threading import Thread

import ngrok
from flask import Flask, request, Response

from agentmail import AgentMail
from agentmail_toolkit.openai import AgentMailToolkit
from agents import Agent, Runner


port = 8080
domain = os.getenv("WEBHOOK_DOMAIN")
inbox = f"{os.getenv('INBOX_USERNAME')}@agentmail.to"

listener = ngrok.forward(port, domain=domain, authtoken_from_env=True)
app = Flask(__name__)

client = AgentMail()

instructions = f"""
You are an email agent. Your name is AgentMail. Your email address is {inbox}.
Respond as if you are writing an email. Do not include the subject, only the body.
"""

agent = Agent(
    name="Email Agent",
    instructions=instructions,
    tools=AgentMailToolkit(client).get_tools(),
)

@app.route("/webhooks", methods=["POST"])
def receive_webhook():
    Thread(target=process_webhook, args=(request.json,)).start()
    return Response(status=200)


def process_webhook(payload):
    email = payload["message"]

    prompt = f"""
From: {email["from"]}
Subject: {email["subject"]}
Body:\n{email["text"]}
"""
    print("Prompt:\n\n", prompt, "\n")

    response = asyncio.run(Runner.run(agent, prompt))
    print("Response:\n\n", response.final_output, "\n")

    client.messages.reply(inbox_id=inbox, message_id=email["message_id"], text=response.final_output)


if __name__ == "__main__":
    print(f"Inbox: {inbox}\n")

    app.run(port=port)
