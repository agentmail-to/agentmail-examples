import os
import json
import time

from agentmail import AgentMail
from openai import OpenAI

agentmail = AgentMail(api_key=os.environ["AGENTMAIL_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

FIRM_NAME = os.environ.get("FIRM_NAME", "Smith & Associates")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "30"))

QUESTIONNAIRE = """Thank you for reaching out to {firm_name}.

To help us understand your situation, please reply with the following information:

1. Brief description of your legal issue
2. When did this issue arise? (approximate date)
3. Have you consulted with another attorney about this matter?
4. What outcome are you hoping to achieve?
5. Your full name and phone number

We will review your information and have the appropriate attorney follow up within 24 hours.

{firm_name} Intake Team"""

CLASSIFY_PROMPT = """You are a legal intake assistant for {firm_name}.

Analyze this potential client's intake response and extract structured information.

Response:
{text}

Return JSON:
{{
  "case_type": "personal-injury"|"employment"|"contract"|"family"|"criminal"|"other",
  "summary": "2-3 sentence summary of the case",
  "client_name": "extracted name or unknown",
  "phone": "extracted phone or unknown",
  "date_of_incident": "extracted date or unknown",
  "urgency": "high"|"medium"|"low",
  "statute_concern": true|false,
  "qualified": true|false,
  "qualification_reason": "why qualified or not"
}}"""


def load_attorneys(path: str = "attorneys.json") -> dict:
    with open(path) as f:
        return json.load(f)


def classify_intake(text: str) -> dict:
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": CLASSIFY_PROMPT.format(
            firm_name=FIRM_NAME, text=text
        )}],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def route_to_attorney(inbox_id: str, case: dict, original_msg, attorneys: dict):
    case_type = case.get("case_type", "other")
    attorney = attorneys.get(case_type, attorneys.get("other"))
    if not attorney:
        print(f"No attorney configured for case type: {case_type}")
        return

    agentmail.messages.send(
        inbox_id=inbox_id,
        to=[attorney["email"]],
        subject=f"[New Lead] {case_type.title()}: {case.get('client_name', 'Unknown')}",
        text=(
            f"New intake from: {original_msg.from_address}\n"
            f"Client: {case.get('client_name', 'Unknown')}\n"
            f"Phone: {case.get('phone', 'Unknown')}\n"
            f"Case type: {case_type}\n"
            f"Urgency: {case.get('urgency', 'medium')}\n"
            f"Statute concern: {'Yes' if case.get('statute_concern') else 'No'}\n\n"
            f"Summary: {case.get('summary', '')}\n\n"
            f"Original message:\n{original_msg.text}"
        ),
        labels=["routed", case_type],
    )
    print(f"Routed to {attorney['name']} ({attorney['email']})")


def handle_messages(inbox_id: str, attorneys: dict):
    messages = agentmail.messages.list(inbox_id=inbox_id, labels=["unread"])
    for msg in messages.data:
        text = msg.text or ""
        sender = msg.from_address

        has_questionnaire_response = len(text.strip()) > 50

        agentmail.messages.update(
            inbox_id=inbox_id,
            message_id=msg.id,
            remove_labels=["unread"],
        )

        if not has_questionnaire_response:
            agentmail.messages.reply(
                inbox_id=inbox_id,
                message_id=msg.id,
                text=QUESTIONNAIRE.format(firm_name=FIRM_NAME),
            )
            agentmail.messages.update(
                inbox_id=inbox_id,
                message_id=msg.id,
                add_labels=["questionnaire-sent"],
            )
            print(f"Sent questionnaire to {sender}")
        else:
            case = classify_intake(text)
            labels = ["details-received", case.get("case_type", "other")]
            if case.get("qualified"):
                labels.append("qualified")
                route_to_attorney(inbox_id, case, msg, attorneys)
                agentmail.messages.reply(
                    inbox_id=inbox_id,
                    message_id=msg.id,
                    text=f"Thank you for providing that information. An attorney from our {case.get('case_type', '').replace('-', ' ')} team will contact you within 24 hours.\n\n{FIRM_NAME}",
                )
                labels.append("routed")
            else:
                agentmail.messages.reply(
                    inbox_id=inbox_id,
                    message_id=msg.id,
                    text=f"Thank you for reaching out. After reviewing your information, we may not be the best fit for your matter. We recommend consulting with a specialist in this area.\n\n{FIRM_NAME}",
                )
            agentmail.messages.update(
                inbox_id=inbox_id,
                message_id=msg.id,
                add_labels=labels,
            )
            print(f"Processed intake from {sender}: {case.get('case_type')} (qualified: {case.get('qualified')})")


def main():
    inbox = agentmail.inboxes.create(display_name=f"{FIRM_NAME} Intake")
    print(f"Intake inbox created: {inbox.email}")

    attorneys = load_attorneys()
    print(f"Routing configured for {len(attorneys)} case types\n")

    while True:
        handle_messages(inbox.id, attorneys)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
