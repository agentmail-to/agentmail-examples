import os
import json
import time

from agentmail import AgentMail
from openai import OpenAI

agentmail = AgentMail(api_key=os.environ["AGENTMAIL_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "30"))

REVIEW_PROMPT = """You are a contract review assistant. Compare the following contract text against our standard terms and identify issues.

Our standard terms:
{standard_terms}

Contract text:
{contract_text}

Return JSON:
{{
  "risk_level": "high"|"medium"|"low",
  "clauses": [
    {{
      "clause": "quoted or paraphrased clause from the contract",
      "issue": "what is problematic",
      "risk": "high"|"medium"|"low",
      "suggestion": "suggested alternative language or action"
    }}
  ],
  "summary": "2-3 sentence overall assessment",
  "accept_as_is": true|false
}}"""


def load_standard_terms(path: str = "standard_terms.json") -> str:
    with open(path) as f:
        terms = json.load(f)
    return "\n".join(f"- {t['area']}: {t['requirement']}" for t in terms)


def review_contract(contract_text: str, standard_terms: str) -> dict:
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": REVIEW_PROMPT.format(
            standard_terms=standard_terms, contract_text=contract_text
        )}],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def format_review(review: dict) -> str:
    lines = [
        f"CONTRACT REVIEW - Risk Level: {review['risk_level'].upper()}",
        "=" * 50,
        "",
        review["summary"],
        "",
    ]

    if review.get("accept_as_is"):
        lines.append("Recommendation: This contract is acceptable as-is.")
    else:
        lines.append("FLAGGED CLAUSES:")
        lines.append("")
        for i, clause in enumerate(review.get("clauses", []), 1):
            lines.append(f"{i}. [{clause['risk'].upper()} RISK] {clause['issue']}")
            lines.append(f"   Clause: \"{clause['clause']}\"")
            lines.append(f"   Suggestion: {clause['suggestion']}")
            lines.append("")

    lines.append("---")
    lines.append("This is an automated first-pass review. Consult legal counsel for final decisions.")
    return "\n".join(lines)


def handle_messages(inbox_id: str, standard_terms: str):
    messages = agentmail.messages.list(inbox_id=inbox_id, labels=["unread"])
    for msg in messages.data:
        sender = msg.from_address or ""
        contract_text = msg.text or msg.html or ""

        agentmail.messages.update(
            inbox_id=inbox_id,
            message_id=msg.id,
            remove_labels=["unread"],
        )

        if len(contract_text.strip()) < 100:
            agentmail.messages.reply(
                inbox_id=inbox_id,
                message_id=msg.id,
                text="Please forward the contract text in the email body. The message received was too short to review.",
            )
            continue

        print(f"Reviewing contract from {sender}...")
        review = review_contract(contract_text, standard_terms)
        formatted = format_review(review)

        risk = review.get("risk_level", "medium")
        agentmail.messages.reply(
            inbox_id=inbox_id,
            message_id=msg.id,
            text=formatted,
        )
        agentmail.messages.update(
            inbox_id=inbox_id,
            message_id=msg.id,
            add_labels=["reviewed", f"risk-{risk}"],
        )
        print(f"  Risk: {risk}, Clauses flagged: {len(review.get('clauses', []))}")


def main():
    inbox = agentmail.inboxes.create(display_name="Contract Reviewer")
    print(f"Contract review inbox: {inbox.email}")
    print(f"Forward contracts to this address for review.\n")

    standard_terms = load_standard_terms()

    while True:
        handle_messages(inbox.id, standard_terms)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
