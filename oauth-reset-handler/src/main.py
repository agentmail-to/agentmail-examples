import os
import re
import time
import json

from agentmail import AgentMail
from openai import OpenAI

agentmail = AgentMail(api_key=os.environ["AGENTMAIL_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

MAX_WAIT_SECONDS = int(os.environ.get("MAX_WAIT_SECONDS", "120"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "5"))

EXTRACT_PROMPT = """Extract the verification code, OTP, magic link, or reset link from this email.

Email subject: {subject}
Email body:
{body}

Return JSON:
{{
  "type": "otp"|"magic_link"|"reset_link"|"verification_code"|"none",
  "value": "the extracted code or URL",
  "expires_in": "expiration time if mentioned, otherwise null"
}}"""


def extract_verification(subject: str, body: str) -> dict:
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": EXTRACT_PROMPT.format(
            subject=subject, body=body
        )}],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def create_temp_inbox(label: str = "verification") -> tuple[str, str]:
    inbox = agentmail.inboxes.create(display_name=f"Temp - {label}")
    return inbox.id, inbox.email


def wait_for_verification(inbox_id: str, from_domain: str = None) -> dict:
    elapsed = 0
    while elapsed < MAX_WAIT_SECONDS:
        messages = agentmail.messages.list(inbox_id=inbox_id, labels=["unread"])
        for msg in messages.data:
            sender = msg.from_address or ""
            if from_domain and from_domain not in sender:
                continue

            subject = msg.subject or ""
            body = msg.text or msg.html or ""

            result = extract_verification(subject, body)
            if result.get("type") != "none":
                agentmail.messages.update(
                    inbox_id=inbox_id,
                    message_id=msg.id,
                    add_labels=["processed"],
                    remove_labels=["unread"],
                )
                return result

        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    return {"type": "none", "value": None, "error": "timeout"}


def get_verification_code(
    service_name: str,
    from_domain: str = None,
) -> dict:
    inbox_id, email = create_temp_inbox(label=service_name)
    print(f"Created temp inbox: {email}")
    print(f"Use this email address to trigger the verification flow for {service_name}")
    print(f"Waiting up to {MAX_WAIT_SECONDS}s for verification email...")

    result = wait_for_verification(inbox_id, from_domain=from_domain)

    if result.get("type") != "none":
        print(f"Extracted {result['type']}: {result['value']}")
    else:
        print("Timed out waiting for verification email")

    return {"inbox_id": inbox_id, "email": email, **result}


def cleanup_inbox(inbox_id: str):
    agentmail.inboxes.delete(inbox_id=inbox_id)
    print(f"Cleaned up inbox {inbox_id}")


def main():
    print("OAuth Reset Handler Demo")
    print("========================\n")

    result = get_verification_code(
        service_name="demo-service",
        from_domain=None,
    )

    print(f"\nResult: {json.dumps(result, indent=2)}")

    if input("\nClean up temp inbox? (y/n): ").strip().lower() == "y":
        cleanup_inbox(result["inbox_id"])


if __name__ == "__main__":
    main()
