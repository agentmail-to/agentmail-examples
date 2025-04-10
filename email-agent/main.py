import os
import json
import asyncio
from threading import Thread

import ngrok
from flask import Flask, request, Response

from agentmail_toolkit.openai import AgentMailToolkit
from agents import Agent, Runner


port = 8080
domain = os.getenv("WEBHOOK_DOMAIN")
inbox = f"{os.getenv('INBOX_USERNAME')}@agentmail.io"

listener = ngrok.forward(port, domain=domain, authtoken_from_env=True)
app = Flask(__name__)

agent = Agent(
    name="Email Agent",
    instructions=f"You are an email agent created by AgentMail. Your email address is {inbox}. Reply to the user's message as you deem fit. Get the thread for context. Do not ask for more information, just reply to the user's message at all costs.",
    tools=AgentMailToolkit().get_tools(),
)


@app.route("/webhooks", methods=["POST"])
def receive_webhook():
    Thread(target=process_webhook, args=(request.json,)).start()
    return Response(status=200)


def process_webhook(payload):
    prompt = json.dumps(payload, indent=4)
    print("Prompt:\n\n", prompt, "\n")

    response = asyncio.run(Runner.run(agent, prompt))
    print("Response:\n\n", response.final_output, "\n")


if __name__ == "__main__":
    print(f"Ingress: {listener.url()}")
    print(f"Inbox: {inbox}\n")

    app.run(port=port)
