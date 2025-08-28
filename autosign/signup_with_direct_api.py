"""
Signup automation using direct AgentMail API for verification codes.
This integrates the working simple_agentmail_api.py with browser-use.
"""

import asyncio
import os
import sys
import time
from browser_use.llm import ChatAnthropic
from browser_use import Agent, BrowserSession, BrowserProfile
from pathlib import Path
from dotenv import load_dotenv
from simple_agentmail_api import get_latest_verification_code, get_most_recent_verification_code, get_messages_from_inbox

load_dotenv()

class DirectAPISignupAutomation:
    def __init__(self):
        self.email = os.environ.get('AGENTMAIL_INBOX_ID')
        self.verification_code = None
        
    def setup_browser(self):
        """Setup persistent browser profile"""
        user_data_dir = Path.home() / ".config" / "browseruse" / "profiles" / "persistent"
        user_data_dir.mkdir(parents=True, exist_ok=True)
        
        browser_profile = BrowserProfile(
            user_data_dir=str(user_data_dir),
            keep_alive=True,
            headless=False,
            viewport={"width": 1280, "height": 800},
        )
        
        return BrowserSession(browser_profile=browser_profile)
    
    def setup_llm(self):
        """Setup Anthropic LLM"""
        return ChatAnthropic(
            model="claude-sonnet-4-0",
            api_key=os.environ['ANTHROPIC_API_KEY']
        )
    
    def get_verification_code(self, timeout=120, check_interval=5):
        """
        Wait for and extract verification code from AgentMail using direct API
        
        Args:
            timeout: Total time to wait in seconds
            check_interval: How often to check for new messages
            
        Returns:
            The verification code if found, None otherwise
        """
        print(f"📧 Waiting for verification code in {self.email}...")
        print("⏳ This may take up to 2 minutes...")
        
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                # Use the direct API to get the latest verification code
                code = get_most_recent_verification_code()
                
                if code:
                    print(f"✅ Verification code received: {code}")
                    return code
                    
            except Exception as e:
                print(f"⚠️ Error checking messages: {e}")
                
            # Wait before checking again
            time.sleep(check_interval)
            
        print("❌ No verification code received within timeout")
        return None
    
    def wait_for_fresh_verification_code(self, timeout=120, check_interval=5):
        """
        Wait for a fresh verification code to arrive after signup
        
        Args:
            timeout: Total time to wait in seconds
            check_interval: How often to check for new messages
            
        Returns:
            The fresh verification code if found, None otherwise
        """
        print(f"📧 Waiting for fresh verification code in {self.email}...")
        print("⏳ This may take up to 2 minutes...")
        
        # Get the current number of messages to detect new ones
        initial_messages = get_messages_from_inbox()
        initial_count = len(initial_messages) if initial_messages else 0
        print(f"📊 Initial message count: {initial_count}")
        
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                # Check for new messages
                current_messages = get_messages_from_inbox()
                current_count = len(current_messages) if current_messages else 0
                
                if current_count > initial_count:
                    print(f"📧 New message detected! Count: {initial_count} → {current_count}")
                    
                    # Get the most recent verification code (should be the new one)
                    code = get_most_recent_verification_code()
                    
                    if code:
                        print(f"✅ Fresh verification code received: {code}")
                        return code
                        
            except Exception as e:
                print(f"⚠️ Error checking messages: {e}")
                
            # Wait before checking again
            time.sleep(check_interval)
            
        print("❌ No fresh verification code received within timeout")
        return None
    
    async def signup_with_verification(self, signup_url, signup_task, verification_task):
        """
        Complete signup process with email verification using direct API
        
        Args:
            signup_url: URL of the signup page
            signup_task: Task description for initial signup
            verification_task: Task description for entering verification code
        """
        try:
            print(f"📧 Using email: {self.email}")
            
            # Setup browser and LLM
            browser_session = self.setup_browser()
            llm = self.setup_llm()
            
            # Step 1: Initial signup (focus only on the signup website)
            print(f"\n🚀 Step 1: Starting signup at {signup_url}")
            signup_agent = Agent(
                task=f"{signup_task} Use email: {self.email}. CRITICAL: Stay ONLY on the signup website ({signup_url}), do NOT navigate to any other websites including AgentMail. The email verification will be handled separately.",
                llm=llm,
                browser_session=browser_session,
            )
            
            signup_result = await signup_agent.run()
            print(f"✅ Signup completed: {signup_result}")
            
            # Step 2: Get the most recent verification code
            print(f"\n📧 Step 2: Getting most recent verification code...")
            self.verification_code = self.get_verification_code()
            
            if not self.verification_code:
                print("❌ Failed to get verification code")
                return False
            
            # Step 3: Enter verification code
            print(f"\n🔐 Step 3: Entering verification code: {self.verification_code}")
            verification_agent = Agent(
                task=f"{verification_task} Use code: {self.verification_code}. CRITICAL: DO NOT click any skip buttons, skip links, or skip options. You MUST enter the verification code {self.verification_code} into the verification input field. Stay on the same website and find the verification input field. The verification step is required and cannot be skipped.",
                llm=llm,
                browser_session=browser_session,
            )
            
            verification_result = await verification_agent.run()
            print(f"✅ Verification completed: {verification_result}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error during signup: {e}")
            return False

async def main():
    """Main function to run signup automation"""
    print("🚀 Direct API Signup Automation with AgentMail")
    print("=" * 50)
    
    # Get signup details from command line
    if len(sys.argv) < 2:
        print("🚀 SignupBot - AI Agent Authentication")
        print("=" * 50)
        print("Usage: python signup_with_direct_api.py \"your natural language request\"")
        print("\nExamples:")
        print("  python signup_with_direct_api.py \"sign me up for GitHub\"")
        print("  python signup_with_direct_api.py \"create a dev.to account\"")
        print("  python signup_with_direct_api.py \"sign up for GoDaddy with image CAPTCHA\"")
        print("  python signup_with_direct_api.py \"create account on https://example.com\"")
        print("  python signup_with_direct_api.py \"sign up for Reddit\"")
        print("\nThe bot will automatically:")
        print("  • Navigate to the signup page")
        print("  • Fill in the form with your email")
        print("  • Handle CAPTCHAs and verification")
        print("  • Complete the signup process")
        sys.exit(1)
    
    # Get the natural language request
    user_request = " ".join(sys.argv[1:]).lower()
    print(f"🎯 User Request: {user_request}")
    
    # NLP processing to understand the request
    def parse_nlp_request(request):
        """Parse natural language request to determine service and configuration"""
        
        # Known services mapping
        service_keywords = {
            'github': ['github', 'git hub'],
            'devto': ['dev.to', 'devto', 'dev to'],
            'godaddy': ['godaddy', 'go daddy', 'domain registration'],
            'stackoverflow': ['stack overflow', 'stackoverflow', 'stack overflow'],
            'reddit': ['reddit']
        }
        
        # Check for custom URLs
        import re
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, request)
        
        # Determine service
        for service, keywords in service_keywords.items():
            if any(keyword in request for keyword in keywords):
                return service, None
        
        # If URL found, treat as custom
        if urls:
            return 'custom', urls[0]
        
        # Default to custom if no specific service found
        return 'custom', None
    
    service, custom_url = parse_nlp_request(user_request)
    print(f"🔍 Detected Service: {service}")
    if custom_url:
        print(f"🌐 Custom URL: {custom_url}")
    
    # Service configurations
    services = {
        'reddit': {
            'url': 'https://www.reddit.com/register/',
            'signup_task': 'Go to Reddit signup page and create a new account. Fill in username, password, and email. Complete the signup process and wait for email verification step. IMPORTANT: Stay only on Reddit website, do not navigate to any other websites.',
            'verification_task': 'Find the email verification input field and enter the verification code. DO NOT click any skip buttons or skip the verification step. You must enter the verification code to complete the signup. Submit the form to complete verification.'
        },
        'twitter': {
            'url': 'https://twitter.com/i/flow/signup',
            'signup_task': 'Go to Twitter signup page and create a new account. Fill in name, email, and password. Complete the signup process and wait for email verification step. IMPORTANT: Stay only on Twitter website, do not navigate to any other websites.',
            'verification_task': 'Find the verification code input field and enter the code. DO NOT click any skip buttons or skip the verification step. You must enter the verification code to complete the signup. Submit to complete verification.'
        },
        'github': {
            'url': 'https://github.com/signup',
            'signup_task': 'Go to GitHub signup page and create a new account. Fill in username, email, and password. Complete the signup process and wait for email verification step. IMPORTANT: Stay only on GitHub website, do not navigate to any other websites. Use a unique username like "outstandingheat434" or similar.',
            'verification_task': 'Find the verification code input field and enter the code. DO NOT click any skip buttons or skip the verification step. You must enter the verification code to complete the signup. Submit to complete verification.'
        },
        'stackoverflow': {
            'url': 'https://stackoverflow.com/users/signup',
            'signup_task': 'Go to Stack Overflow signup page and create a new account. Fill in display name, email, and password. Complete the signup process and wait for email verification step. IMPORTANT: Stay only on Stack Overflow website, do not navigate to any other websites. Use a unique display name like "outstandingheat434" or similar.',
            'verification_task': 'Find the verification code input field and enter the code. DO NOT click any skip buttons or skip the verification step. You must enter the verification code to complete the signup. Submit to complete verification.'
        },

        'godaddy': {
            'url': 'https://www.godaddy.com/register',
            'signup_task': 'Go to GoDaddy registration page and create a new account. Fill in email, password, and other required fields. IMPORTANT: If you encounter a CAPTCHA asking to "select all images with traffic lights" or similar, carefully analyze each image and click only the correct ones. Stay only on GoDaddy website, do not navigate to any other websites.',
            'verification_task': 'If there is an email verification step, find the verification code input field and enter the code. DO NOT click any skip buttons or skip the verification step. You must enter the verification code to complete the signup. Submit to complete verification.'
        },
        'devto': {
            'url': 'https://dev.to/enter',
            'signup_task': 'Go to dev.to signup page and create a new account. Fill in username, email, and password. IMPORTANT: If you encounter a reCAPTCHA, look for a "Solve with 2captcha" button and click it. Then wait for 40 seconds for the CAPTCHA to be solved. Once the CAPTCHA is solved, continue with the signup process. Stay only on dev.to website, do not navigate to any other websites.',
            'verification_task': 'If there is an email verification step, find the verification code input field and enter the code. DO NOT click any skip buttons or skip the verification step. You must enter the verification code to complete the signup. Submit to complete verification.'
        },

    }
    
    if service == 'custom':
        if custom_url:
            # Custom URL provided
            service_config = {
                'url': custom_url,
                'signup_task': f'Go to {custom_url} and create a new account. Fill in email, username, and password. Complete the signup process and wait for email verification step. IMPORTANT: Stay only on this website, do not navigate to any other websites.',
                'verification_task': 'If there is an email verification step, find the verification code input field and enter the code. DO NOT click any skip buttons or skip the verification step. You must enter the verification code to complete the signup. Submit to complete verification.'
            }
        else:
            # No URL provided, ask user to be more specific
            print("❌ Please provide a URL or be more specific about which website you want to sign up for.")
            print("Examples:")
            print("  python signup_with_direct_api.py \"sign up for https://example.com\"")
            print("  python signup_with_direct_api.py \"create account on GitHub\"")
            sys.exit(1)
    elif service in services:
        service_config = services[service]
    else:
        print(f"❌ Unknown service: {service}")
        print("Available services:", ", ".join(services.keys()))
        sys.exit(1)
    
    # Run the signup automation
    automation = DirectAPISignupAutomation()
    
    print(f"🎯 Service: {service.upper()}")
    print(f"🌐 URL: {service_config['url']}")
    print(f"📝 Task: {service_config['signup_task']}")
    print("\n" + "=" * 50)
    
    success = await automation.signup_with_verification(
        service_config['url'],
        service_config['signup_task'],
        service_config['verification_task']
    )
    
    if success:
        print("\n🎉 Signup automation completed successfully!")
        print(f"📧 Email used: {automation.email}")
        print(f"🔐 Verification code: {automation.verification_code}")
    else:
        print("\n❌ Signup automation failed")

if __name__ == "__main__":
    asyncio.run(main())
