import os
import asyncio
from threading import Thread

import ngrok
from flask import Flask, request, Response

from agentmail import AgentMail
from agentmail_toolkit.openai import AgentMailToolkit
from agents import WebSearchTool, Agent, Runner


port = 8080
domain = os.getenv("WEBHOOK_DOMAIN")
inbox = f"{os.getenv('INBOX_USERNAME')}@agentmail.to"

listener = ngrok.forward(port, domain=domain, authtoken_from_env=True)
app = Flask(__name__)

client = AgentMail()

instructions = f"""
You are an email sales agent. Your name is AgentMail. Your email address is {inbox}.

When you recieve an email from a sales manager, they should provide you with a product to sell and the name and email address of a sales prospect.
If they do not provide you with this information, ask them for it.
Use the WebSearchTool to find more information about the product.
Once you have all the information you need, send an email to the sales prospect using the send_message tool.
Then generate an appropriate response to the sales manager.

When you receive an email from a sales prospect, evaluate their intent.
If they have questions about the product, answer their questions. Use the WebSearchTool to find the answers.
If they express clear interest or disinterest in the product, send an email to the sales manager using the send_message tool reporting their intent.
Then generate an appropriate response to the sales prospect.

All emails and responses must be plain text. Do not use markdown. Do not use placeholders.
All responses must be in email body format. Do not include the subject, only the body.
"""

agent = Agent(
    name="Sales Agent",
    instructions=instructions,
    tools=AgentMailToolkit(client).get_tools() + [WebSearchTool()],
)

messages = []

@app.route("/webhooks", methods=["POST"])
def receive_webhook():
    Thread(target=process_webhook, args=(request.json,)).start()
    return Response(status=200)


def process_webhook(payload):
    global messages

    email = payload["message"]

    prompt = f"""
From: {email["from"]}
Subject: {email["subject"]}
Body:\n{email["text"]}
"""
    print("Prompt:\n\n", prompt, "\n")

    response = asyncio.run(Runner.run(agent, messages + [{"role": "user", "content": prompt}]))
    print("Response:\n\n", response.final_output, "\n")

    client.messages.reply(inbox_id=inbox, message_id=email["message_id"], text=response.final_output)

    messages = response.to_input_list()


if __name__ == "__main__":
    print(f"Inbox: {inbox}\n")

    app.run(port=port)
