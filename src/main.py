import os
import json
import time

from agentmail import AgentMail
from openai import OpenAI

agentmail = AgentMail(api_key=os.environ["AGENTMAIL_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

HIRING_MANAGER_EMAIL = os.environ["HIRING_MANAGER_EMAIL"]
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "30"))
PASS_THRESHOLD = float(os.environ.get("PASS_THRESHOLD", "0.7"))

SCREENING_PROMPT = """Generate screening questions for a candidate who applied for this role.

Role: {role_title}
Description: {role_description}
Required skills: {required_skills}

The candidate's application:
{application_text}

Return JSON:
{{
  "personalized_intro": "one sentence acknowledging something specific from their application",
  "questions": ["question 1", "question 2", "question 3"]
}}"""

SCORE_PROMPT = """Score this candidate's screening responses for the role of {role_title}.

Required skills: {required_skills}
Screening criteria: {criteria}

Candidate responses:
{responses}

Return JSON:
{{
  "overall_score": 0.0 to 1.0,
  "strengths": ["strength 1", "strength 2"],
  "concerns": ["concern 1"],
  "summary": "2-3 sentence assessment",
  "recommendation": "advance"|"reject"|"maybe"
}}"""


def load_job_config(path: str = "job_config.json") -> dict:
    with open(path) as f:
        return json.load(f)


def llm_json(prompt: str) -> dict:
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def handle_messages(inbox_id: str, config: dict, tracker: dict):
    messages = agentmail.messages.list(inbox_id=inbox_id, labels=["unread"])
    for msg in messages.data:
        sender = msg.from_address or ""
        text = msg.text or ""

        agentmail.messages.update(
            inbox_id=inbox_id,
            message_id=msg.id,
            remove_labels=["unread"],
        )

        if sender not in tracker:
            result = llm_json(SCREENING_PROMPT.format(
                role_title=config["role_title"],
                role_description=config["role_description"],
                required_skills=", ".join(config["required_skills"]),
                application_text=text,
            ))

            questions_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(result["questions"]))
            agentmail.messages.reply(
                inbox_id=inbox_id,
                message_id=msg.id,
                text=(
                    f"Thank you for applying for the {config['role_title']} position.\n\n"
                    f"{result['personalized_intro']}\n\n"
                    f"To move forward, please answer these screening questions:\n\n"
                    f"{questions_text}\n\n"
                    f"Please reply to this email with your answers."
                ),
            )
            tracker[sender] = {"stage": "screening", "message_id": msg.id}
            agentmail.messages.update(inbox_id=inbox_id, message_id=msg.id, add_labels=["applied", "screening"])
            print(f"Sent screening questions to {sender}")

        elif tracker[sender]["stage"] == "screening":
            score = llm_json(SCORE_PROMPT.format(
                role_title=config["role_title"],
                required_skills=", ".join(config["required_skills"]),
                criteria=config.get("screening_criteria", "general fit"),
                responses=text,
            ))

            tracker[sender]["stage"] = "scored"
            tracker[sender]["score"] = score

            if score.get("recommendation") == "advance" or score.get("overall_score", 0) >= PASS_THRESHOLD:
                agentmail.messages.send(
                    inbox_id=inbox_id,
                    to=[HIRING_MANAGER_EMAIL],
                    subject=f"[Qualified Candidate] {config['role_title']}: {sender}",
                    text=(
                        f"Candidate: {sender}\n"
                        f"Score: {score['overall_score']:.0%}\n"
                        f"Recommendation: {score['recommendation']}\n\n"
                        f"Strengths: {', '.join(score.get('strengths', []))}\n"
                        f"Concerns: {', '.join(score.get('concerns', []))}\n\n"
                        f"Summary: {score['summary']}\n\n"
                        f"Screening responses:\n{text}"
                    ),
                    labels=["qualified", "forwarded"],
                )
                agentmail.messages.reply(
                    inbox_id=inbox_id,
                    message_id=msg.id,
                    text=f"Thank you for your responses. We are impressed with your background and would like to move forward. Our hiring manager will be in touch shortly.\n\nBest regards",
                )
                agentmail.messages.update(inbox_id=inbox_id, message_id=msg.id, add_labels=["qualified"])
                print(f"Qualified: {sender} (score: {score['overall_score']:.0%})")
            else:
                agentmail.messages.reply(
                    inbox_id=inbox_id,
                    message_id=msg.id,
                    text=f"Thank you for taking the time to answer our questions. After careful review, we have decided to move forward with other candidates whose experience more closely aligns with our current needs. We wish you the best in your search.\n\nBest regards",
                )
                agentmail.messages.update(inbox_id=inbox_id, message_id=msg.id, add_labels=["rejected"])
                print(f"Rejected: {sender} (score: {score['overall_score']:.0%})")


def main():
    config = load_job_config()
    inbox = agentmail.inboxes.create(display_name=f"Apply: {config['role_title']}")
    print(f"Hiring inbox: {inbox.email}")
    print(f"Post this as the application email for: {config['role_title']}")
    print(f"Qualified candidates forwarded to: {HIRING_MANAGER_EMAIL}\n")

    tracker: dict = {}

    while True:
        handle_messages(inbox.id, config, tracker)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
