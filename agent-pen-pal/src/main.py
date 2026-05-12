import os
import json
import time

from agentmail import AgentMail
from openai import OpenAI

agentmail = AgentMail(api_key=os.environ["AGENTMAIL_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

REPLY_PROMPT = """You are {name}, {personality}.

You are having an email conversation about: {topic}

Conversation so far:
{history}

Write your next reply. Keep it under 200 words. Stay in character. Be thoughtful and build on what was said."""


def load_config(path: str = "config.json") -> dict:
    with open(path) as f:
        return json.load(f)


def generate_reply(name: str, personality: str, topic: str, history: str) -> str:
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": REPLY_PROMPT.format(
            name=name, personality=personality, topic=topic, history=history
        )}],
    )
    return resp.choices[0].message.content


def get_thread_history(thread_id: str) -> str:
    thread = agentmail.threads.get(thread_id=thread_id)
    lines = []
    for msg in thread.messages:
        sender = msg.from_address or "Unknown"
        lines.append(f"From: {sender}\n{msg.text or ''}\n")
    return "\n---\n".join(lines)


def main():
    config = load_config()
    topic = config["topic"]
    agent_a = config["agent_a"]
    agent_b = config["agent_b"]
    max_turns = config.get("max_turns", 10)
    delay = config.get("delay_seconds", 10)

    inbox_a = agentmail.inboxes.create(display_name=agent_a["name"])
    inbox_b = agentmail.inboxes.create(display_name=agent_b["name"])

    print(f"Agent A ({agent_a['name']}): {inbox_a.email}")
    print(f"Agent B ({agent_b['name']}): {inbox_b.email}")
    print(f"Topic: {topic}\n")

    first_message = generate_reply(
        agent_a["name"], agent_a["personality"], topic, "(Starting the conversation)"
    )
    msg = agentmail.messages.send(
        inbox_id=inbox_a.id,
        to=[inbox_b.email],
        subject=f"Let's discuss: {topic}",
        text=first_message,
        labels=["sent", "turn-1"],
    )
    print(f"Turn 1 - {agent_a['name']}:\n{first_message}\n")

    thread_id = None
    current_inbox = inbox_b
    current_agent = agent_b
    other_inbox = inbox_a
    turn = 2

    time.sleep(delay)

    while turn <= max_turns:
        messages = agentmail.messages.list(inbox_id=current_inbox.id, labels=["unread"])
        if not messages.data:
            time.sleep(5)
            continue

        incoming = messages.data[0]
        if not thread_id:
            thread_id = incoming.thread_id

        agentmail.messages.update(
            inbox_id=current_inbox.id,
            message_id=incoming.id,
            add_labels=["received"],
            remove_labels=["unread"],
        )

        history = get_thread_history(thread_id) if thread_id else incoming.text or ""
        reply_text = generate_reply(
            current_agent["name"], current_agent["personality"], topic, history
        )

        agentmail.messages.reply(
            inbox_id=current_inbox.id,
            message_id=incoming.id,
            text=reply_text,
        )
        print(f"Turn {turn} - {current_agent['name']}:\n{reply_text}\n")

        current_inbox, other_inbox = other_inbox, current_inbox
        current_agent = agent_a if current_agent == agent_b else agent_b
        turn += 1
        time.sleep(delay)

    print(f"Conversation complete after {max_turns} turns.")


if __name__ == "__main__":
    main()
