import os
import subprocess
import time
import shlex

from agentmail import AgentMail

from config import ALLOWED_COMMANDS, COMMAND_TIMEOUT, ALLOWED_SENDERS

agentmail = AgentMail(api_key=os.environ["AGENTMAIL_API_KEY"])

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "10"))


def is_command_allowed(command: str) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if not parts:
        return False
    base_cmd = parts[0]
    return base_cmd in ALLOWED_COMMANDS


def is_sender_allowed(sender: str) -> bool:
    if not ALLOWED_SENDERS:
        return True
    return sender in ALLOWED_SENDERS


def execute_command(command: str) -> tuple[str, int]:
    try:
        parts = shlex.split(command)
        result = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            shell=False,
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        return output.strip() or "(no output)", result.returncode
    except subprocess.TimeoutExpired:
        return f"Command timed out after {COMMAND_TIMEOUT} seconds", 1
    except Exception as e:
        return f"Error: {str(e)}", 1


def handle_messages(inbox_id: str):
    messages = agentmail.messages.list(inbox_id=inbox_id, labels=["unread"])
    for msg in messages.data:
        sender = msg.from_address
        command = (msg.subject or "").strip()

        agentmail.messages.update(
            inbox_id=inbox_id,
            message_id=msg.id,
            remove_labels=["unread"],
        )

        if not command:
            agentmail.messages.reply(
                inbox_id=inbox_id,
                message_id=msg.id,
                text="Put the command in the email subject line.",
            )
            continue

        if not is_sender_allowed(sender):
            agentmail.messages.update(
                inbox_id=inbox_id,
                message_id=msg.id,
                add_labels=["blocked"],
            )
            print(f"Blocked command from unauthorized sender: {sender}")
            continue

        if not is_command_allowed(command):
            agentmail.messages.reply(
                inbox_id=inbox_id,
                message_id=msg.id,
                text=f"Command not allowed: {command}\n\nAllowed commands: {', '.join(ALLOWED_COMMANDS)}",
            )
            agentmail.messages.update(
                inbox_id=inbox_id,
                message_id=msg.id,
                add_labels=["blocked"],
            )
            print(f"Blocked disallowed command: {command}")
            continue

        print(f"Executing: {command} (from {sender})")
        output, exit_code = execute_command(command)

        status = "OK" if exit_code == 0 else f"EXIT {exit_code}"
        agentmail.messages.reply(
            inbox_id=inbox_id,
            message_id=msg.id,
            text=f"$ {command}\n\n{output}\n\n[{status}]",
        )
        label = "executed" if exit_code == 0 else "error"
        agentmail.messages.update(
            inbox_id=inbox_id,
            message_id=msg.id,
            add_labels=[label],
        )
        print(f"  Result: {status}")


def main():
    inbox = agentmail.inboxes.create(display_name="CLI Agent")
    print(f"CLI inbox created: {inbox.email}")
    print(f"Send commands in the email subject line.")
    print(f"Allowed commands: {', '.join(ALLOWED_COMMANDS)}\n")

    while True:
        handle_messages(inbox.id)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
