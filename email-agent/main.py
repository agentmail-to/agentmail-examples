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

listener = ngrok.forward(port, domain=domain, authtoken_from_env=True)
app = Flask(__name__)

agent = Agent(
    name="Email Agent",
    instructions="You are an email agent created by AgentMail. Reply to the user's email as you deem fit.",
    tools=AgentMailToolkit().get_tools(),
)


@app.route("/webhooks", methods=["POST"])
def receive_webhook():
    payload = json.dumps(request.json, indent=4)
    print("Payload:\n\n", payload, "\n")

    Thread(target=process_webhook, args=(payload,)).start()

    return Response(status=200)


def process_webhook(payload):
    result = asyncio.run(Runner.run(agent, payload))
    print("Response:\n\n", result.final_output, "\n")


if __name__ == "__main__":
    print(f"Ingress: {listener.url()}")
    app.run(port=port)
