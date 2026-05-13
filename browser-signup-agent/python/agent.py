"""
AgentMail Browser Signup Agent — sign up + verify on any site that emails you.

Most of the web is gated behind email verification. Without an inbox a browser
agent gets stuck on signup walls, OTP pages, and magic links. AgentMail gives
the agent its own inbox so it can complete the entire flow autonomously:

  1. Spin up a Browser Use agent armed with two AgentMail tools:
     - get_email_address() — returns the inbox address to fill into signup forms
     - get_latest_email() — fetches the verification email (code or link)
  2. Hand it a task description.
  3. Let it drive the browser end-to-end.

Run:
    pip install -r requirements.txt
    cp .env.example .env   # then fill in your keys
    python agent.py
"""

import asyncio
import os

from agentmail import AsyncAgentMail
from browser_use import Agent, Browser, ChatAnthropic
from dotenv import load_dotenv

from email_tools import EmailTools

load_dotenv()

# --- config -------------------------------------------------------------------

AGENTMAIL_API_KEY = os.environ["AGENTMAIL_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT_SECONDS", "120"))
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"

# Pick a default task that exercises the full flow (signup + email verify).
# Override TASK in .env to point the agent at any other site.
DEFAULT_TASK = (
    "Go to https://news.ycombinator.com/login and create a new Hacker News account. "
    "Use get_email_address for the email field. Make up a username and password. "
    "After submitting, if a verification email is sent, call get_latest_email to "
    "retrieve the verification link, then click it. When done, summarize the "
    "credentials you used (without echoing the password verbatim)."
)
TASK = os.getenv("TASK", DEFAULT_TASK)


# --- main ---------------------------------------------------------------------


async def main() -> None:
    print(f"📋 Task: {TASK[:120]}{'…' if len(TASK) > 120 else ''}\n")

    # 1. Create a fresh inbox for this agent run.
    email_client = AsyncAgentMail(api_key=AGENTMAIL_API_KEY)
    inbox = await email_client.inboxes.create()
    print(f"📬 Agent inbox: {inbox.email}\n")

    # 2. Wire the inbox into Browser Use as agent tools.
    tools = EmailTools(email_client=email_client, inbox=inbox, email_timeout=EMAIL_TIMEOUT)

    # 3. Configure the LLM and the browser.
    #    ChatAnthropic reads ANTHROPIC_API_KEY from env automatically.
    llm = ChatAnthropic(model=MODEL)
    browser = Browser(headless=HEADLESS)

    # 4. Run. Always clean up the inbox afterward so we don't pile up against
    #    the AgentMail account's inbox limit. Disable cleanup with
    #    KEEP_INBOX=true in .env if you want to inspect the inbox post-run.
    agent = Agent(task=TASK, tools=tools, llm=llm, browser=browser)
    print("🤖 Agent starting…\n")
    try:
        result = await agent.run()
        print("\n✅ Agent finished.\n")
        print(f"Result: {result}\n")
    finally:
        if os.getenv("KEEP_INBOX", "false").lower() != "true":
            try:
                await email_client.inboxes.delete(inbox.inbox_id)
                print(f"🧹 Deleted ephemeral inbox {inbox.email}")
            except Exception as e:
                print(f"⚠️  Couldn't delete inbox: {e}")


if __name__ == "__main__":
    asyncio.run(main())
