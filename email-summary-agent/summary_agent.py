"""
Email summary agent that generates daily summaries using AI.
"""

import os
import time
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
from openai import OpenAI, OpenAIError, RateLimitError, APITimeoutError


class SummaryAgent:
    """AI agent that summarizes daily emails."""

    def __init__(self, agentmail_client, inbox_id: str, inbox_username: str, summary_recipient_email: str):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.agentmail = agentmail_client
        self.inbox_id = inbox_id
        self.inbox_username = inbox_username
        self.summary_recipient_email = summary_recipient_email

    def fetch_todays_emails(self, max_retries: int = 3) -> List[Dict]:
        """Fetch all emails from today from the AgentMail inbox with retry logic."""

        # Get start of today in UTC (timezone-aware)
        from datetime import timezone
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        for attempt in range(max_retries):
            try:
                # List messages from today - pass datetime object, not string
                response = self.agentmail.inboxes.messages.list(
                    inbox_id=self.inbox_id,
                    after=today_start,
                    limit=100  # Adjust as needed
                )

                emails = []
                for message in response.messages:
                    # Fetch full message content with retry for individual messages
                    full_message = None
                    for msg_attempt in range(2):  # Retry individual message fetches
                        try:
                            full_message = self.agentmail.inboxes.messages.get(
                                inbox_id=self.inbox_id,
                                message_id=message.message_id
                            )
                            break
                        except Exception as msg_err:
                            if msg_attempt == 0:
                                print(f"Retrying message fetch for {message.message_id}: {msg_err}")
                                time.sleep(1)
                            else:
                                print(f"Failed to fetch message {message.message_id}: {msg_err}")
                                continue

                    if not full_message:
                        continue

                    # Convert datetime to ISO string for consistency
                    received_at = full_message.created_at
                    if hasattr(received_at, 'isoformat'):
                        received_at = received_at.isoformat()

                    # Handle from_ field - could be string or object
                    from_email = 'unknown@example.com'
                    from_name = ''
                    if hasattr(full_message, 'from_'):
                        if isinstance(full_message.from_, str):
                            from_email = full_message.from_
                        elif hasattr(full_message.from_, 'email'):
                            from_email = full_message.from_.email
                            from_name = full_message.from_.name if hasattr(full_message.from_, 'name') else ''

                    emails.append({
                        'from_email': from_email,
                        'from_name': from_name,
                        'subject': full_message.subject or 'No Subject',
                        'body': full_message.text or full_message.html or '',
                        'received_at': received_at
                    })

                print(f"Fetched {len(emails)} emails from AgentMail inbox")
                return emails

            except Exception as e:
                print(f"Error fetching emails from AgentMail (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print("Max retries reached. Failed to fetch emails.")
                    import traceback
                    traceback.print_exc()
                    return []

        return []

    def generate_summary(self, emails: List[Dict], max_retries: int = 3) -> Optional[str]:
        """Generate a summary of all emails using AI with retry logic."""

        if not emails:
            return "No emails received today."

        # Prepare email content for AI
        email_content = self._format_emails_for_ai(emails)

        # Use OpenAI to generate summary
        system_prompt = """You are an executive assistant that creates concise daily email summaries.

Your summary should:
- Group emails by category (urgent, meetings, requests, FYI, etc.)
- Highlight action items and deadlines
- Note important senders
- Be concise but informative
- Use bullet points for easy scanning
- Flag anything that needs immediate attention

Format the summary in a professional, easy-to-read style."""

        user_prompt = f"""Please summarize these {len(emails)} emails received today:

{email_content}

Create a comprehensive daily email summary."""

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    timeout=60.0  # 60 second timeout
                )

                return response.choices[0].message.content

            except RateLimitError as e:
                print(f"OpenAI rate limit hit (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait_time = 10 * (2 ** attempt)  # 10s, 20s, 40s
                    print(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    print("Max retries reached. Rate limit exceeded.")
                    return None

            except APITimeoutError as e:
                print(f"OpenAI API timeout (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait_time = 5 * (2 ** attempt)  # 5s, 10s, 20s
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print("Max retries reached. API timeout.")
                    return None

            except OpenAIError as e:
                print(f"OpenAI API error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait_time = 3 * (2 ** attempt)  # 3s, 6s, 12s
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print("Max retries reached. OpenAI API error.")
                    import traceback
                    traceback.print_exc()
                    return None

            except Exception as e:
                print(f"Unexpected error generating summary: {e}")
                import traceback
                traceback.print_exc()
                return None

        return None

    def _format_emails_for_ai(self, emails: List[Dict]) -> str:
        """Format emails into a readable format for AI processing."""

        formatted = []
        for i, email in enumerate(emails, 1):
            email_text = f"""
Email #{i}
From: {email.get('from_email', 'Unknown')}
Subject: {email.get('subject', 'No Subject')}
Time: {email.get('received_at', 'Unknown')}

{email.get('body', 'No content')}

---
"""
            formatted.append(email_text)

        return "\n".join(formatted)

    def create_summary_email(self, emails: List[Dict], summary_date: date) -> Optional[str]:
        """Create a formatted summary email."""

        # Generate AI summary
        ai_summary = self.generate_summary(emails)

        if ai_summary is None:
            # AI summary generation failed
            return None

        # Create email header
        date_str = summary_date.strftime("%A, %B %d, %Y")

        summary_email = f"""DAILY EMAIL SUMMARY
{date_str}

Total Emails Received: {len(emails)}

{ai_summary}

---

DETAILED EMAIL LIST
"""

        # Add brief details of each email
        for i, email in enumerate(emails, 1):
            time_str = email.get('received_at', 'Unknown time')
            if time_str != 'Unknown time':
                try:
                    dt = datetime.fromisoformat(time_str)
                    time_str = dt.strftime("%I:%M %p")
                except:
                    pass

            summary_email += f"""
{i}. [{time_str}] From: {email.get('from_email', 'Unknown')}
   Subject: {email.get('subject', 'No Subject')}
"""

        summary_email += f"""

---
This summary was generated automatically by Email Summary Agent.
Inbox: {self.inbox_username}@agentmail.to
"""

        return summary_email

    def send_summary(self, summary_date: date = None):
        """Fetch today's emails and send the daily summary."""

        if summary_date is None:
            summary_date = date.today()

        date_str = summary_date.strftime("%Y-%m-%d")

        try:
            # Fetch emails from AgentMail inbox
            emails = self.fetch_todays_emails()

            if not emails:
                print("No emails to summarize today")
                return

            # Create summary
            summary_content = self.create_summary_email(emails, summary_date)

            if summary_content is None:
                # AI summary generation failed - send error notification
                print("AI summary generation failed. Sending error notification to user.")
                self._send_error_notification(
                    date_str,
                    f"Failed to generate AI summary for {len(emails)} emails. Please check the application logs.",
                    len(emails)
                )
                return

            # Send via AgentMail
            subject = f"Daily Email Summary - {date_str}"

            self.agentmail.inboxes.messages.send(
                inbox_id=self.inbox_id,
                to=self.summary_recipient_email,
                subject=subject,
                text=summary_content
            )

            print(f"Sent summary of {len(emails)} emails to {self.summary_recipient_email}")

        except Exception as e:
            print(f"Error sending summary: {e}")
            import traceback
            traceback.print_exc()

            # Try to send error notification
            try:
                self._send_error_notification(
                    date_str,
                    f"An error occurred while generating your daily email summary: {str(e)}"
                )
            except Exception as notify_err:
                print(f"Failed to send error notification: {notify_err}")

    def _send_error_notification(self, date_str: str, error_message: str, email_count: int = 0):
        """Send an error notification to the user when summary generation fails."""
        try:
            subject = f"⚠️ Email Summary Failed - {date_str}"
            body = f"""EMAIL SUMMARY ERROR NOTIFICATION
{date_str}

{error_message}

{"Emails received: " + str(email_count) if email_count > 0 else ""}

The Email Summary Agent encountered an error and could not generate your daily summary.
Please check the application logs for more details.

---
This is an automated error notification from Email Summary Agent.
Inbox: {self.inbox_username}@agentmail.to
"""

            self.agentmail.inboxes.messages.send(
                inbox_id=self.inbox_id,
                to=self.summary_recipient_email,
                subject=subject,
                text=body
            )

            print(f"Sent error notification to {self.summary_recipient_email}")

        except Exception as e:
            print(f"Failed to send error notification: {e}")

    def generate_category_breakdown(self, emails: List[Dict]) -> Dict:
        """Use AI to categorize emails."""

        if not emails:
            return {}

        email_list = "\n".join([
            f"{i}. From: {email.get('from_email')} - Subject: {email.get('subject')}"
            for i, email in enumerate(emails, 1)
        ])

        system_prompt = """Categorize these emails into groups like: Urgent, Meetings, Requests,
FYI/Updates, Sales/Marketing, Personal, etc. Return as JSON with category names as keys
and lists of email numbers as values."""

        user_prompt = f"""Categorize these emails:\n\n{email_list}"""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )

        import json
        return json.loads(response.choices[0].message.content)
