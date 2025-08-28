"""
Simple script to get messages from AgentMail using the API directly.
"""

import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

def get_messages_from_inbox():
    """Get messages from AgentMail inbox using the API"""
    
    api_key = os.environ.get('AGENTMAIL_API_KEY')
    inbox_id = os.environ.get('AGENTMAIL_INBOX_ID')
    
    if not api_key or not inbox_id:
        print("❌ Missing API key or inbox ID")
        return None
    
    # API endpoint
    url = f"https://api.agentmail.to/v0/inboxes/{inbox_id}/messages"
    
    # Headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"📧 Fetching messages from inbox: {inbox_id}")
        print(f"🔗 API URL: {url}")
        
        response = requests.get(url, headers=headers)
        
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success! Found {len(data.get('messages', []))} messages")
            
            # Print each message
            for i, message in enumerate(data.get('messages', []), 1):
                print(f"\n📨 Message {i}:")
                print(f"   Subject: {message.get('subject', 'No subject')}")
                print(f"   Preview: {message.get('preview', 'No preview')}")
                print(f"   From: {message.get('from', 'Unknown')}")
                print(f"   To: {message.get('to', 'Unknown')}")
                print(f"   Message ID: {message.get('message_id', 'Unknown')}")
                
                # Check if it's a verification email
                subject = message.get('subject', '').lower()
                preview = message.get('preview', '').lower()
                
                verification_keywords = [
                    'verification', 'verify', 'confirm', 'confirmation',
                    'code', 'otp', 'pin', 'activate', 'activation'
                ]
                
                is_verification = any(keyword in subject or keyword in preview for keyword in verification_keywords)
                
                if is_verification:
                    print("   ✅ VERIFICATION EMAIL DETECTED")
                    
                    # Try to extract verification code from both subject and preview
                    import re
                    patterns = [
                        r'launch code[^0-9]*(\d{4,10})',  # GitHub specific - check first
                        r'(\d{4,10})[^0-9]*launch',  # GitHub specific - check first
                        r'verification code[:\s]*(\d{4,10})',
                        r'code[:\s]*(\d{4,10})',
                        r'(\d{4,10})[^0-9]*is your',
                        r'enter[^0-9]*(\d{4,10})',
                        r'(\d{4,10})',  # General pattern - check last
                    ]
                    
                    # Check subject first (Reddit puts codes in subject)
                    for pattern in patterns:
                        match = re.search(pattern, subject, re.IGNORECASE)
                        if match:
                            code = match.group(1)
                            if len(code) >= 4 and len(code) <= 10 and code.isdigit():
                                print(f"   🔐 VERIFICATION CODE (from subject): {code}")
                                break
                    
                    # If not found in subject, check preview
                    if 'preview' in message and message['preview']:
                        for pattern in patterns:
                            match = re.search(pattern, preview, re.IGNORECASE)
                            if match:
                                code = match.group(1)
                                if len(code) >= 4 and len(code) <= 10 and code.isdigit():
                                    print(f"   🔐 VERIFICATION CODE (from preview): {code}")
                                    break
                else:
                    print("   ❌ Not a verification email")
                    
            return data.get('messages', [])
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None

def get_latest_verification_code():
    """Get the latest verification code from the inbox"""
    messages = get_messages_from_inbox()
    
    if not messages:
        return None
    
    # Look for verification emails in order (newest first based on API response order)
    for message in messages:  # API returns newest messages first
        subject = message.get('subject', '').lower()
        preview = message.get('preview', '').lower()
        
        verification_keywords = [
            'verification', 'verify', 'confirm', 'confirmation',
            'code', 'otp', 'pin', 'activate', 'activation'
        ]
        
        if any(keyword in subject or keyword in preview for keyword in verification_keywords):
            # Extract verification code from both subject and preview
            import re
            patterns = [
                r'launch code[:\s]*(\d+)',  # GitHub specific - check first
                r'(\d+)[^0-9]*launch',  # GitHub specific - check first
                r'verification code[:\s]*(\d+)',
                r'code[:\s]*(\d+)',
                r'(\d+)[^0-9]*is your',
                r'enter[^0-9]*(\d+)',
                r'(\d+)',  # General pattern - check last
            ]
            
            # Check subject first (Reddit puts codes in subject)
            for pattern in patterns:
                match = re.search(pattern, subject, re.IGNORECASE)
                if match:
                    code = match.group(1)
                    if code.isdigit() and len(code) >= 2:  # Any length 2 or more
                        print(f"🎉 Found verification code (from subject): {code}")
                        print(f"📧 Email subject: {message.get('subject', 'No subject')}")
                        return code
            
            # If not found in subject, check preview
            if preview:
                for pattern in patterns:
                    match = re.search(pattern, preview, re.IGNORECASE)
                    if match:
                        code = match.group(1)
                        if code.isdigit() and len(code) >= 2:  # Any length 2 or more
                            print(f"🎉 Found verification code (from preview): {code}")
                            print(f"📧 Email preview: {preview}")
                            return code
    
    print("❌ No verification code found")
    return None

def get_most_recent_verification_code():
    """Get the most recent verification code by checking message timestamps"""
    messages = get_messages_from_inbox()
    
    if not messages:
        return None
    
    verification_codes = []
    
    # Collect all verification codes with their message info
    for message in messages:
        subject = message.get('subject', '').lower()
        preview = message.get('preview', '').lower()
        
        verification_keywords = [
            'verification', 'verify', 'confirm', 'confirmation',
            'code', 'otp', 'pin', 'activate', 'activation'
        ]
        
        if any(keyword in subject or keyword in preview for keyword in verification_keywords):
            # Extract verification code
            import re
            patterns = [
                r'launch code[:\s]*(\d+)',  # GitHub specific - check first
                r'(\d+)[^0-9]*launch',  # GitHub specific - check first
                r'verification code[:\s]*(\d+)',
                r'code[:\s]*(\d+)',
                r'(\d+)[^0-9]*is your',
                r'enter[^0-9]*(\d+)',
                r'(\d+)',  # General pattern - check last
            ]
            
            # Check subject first
            for pattern in patterns:
                match = re.search(pattern, subject, re.IGNORECASE)
                if match:
                    code = match.group(1)
                    if code.isdigit() and len(code) >= 2:  # Any length 2 or more
                        verification_codes.append({
                            'code': code,
                            'subject': message.get('subject', ''),
                            'message_id': message.get('message_id', ''),
                            'from': message.get('from', ''),
                            'index': len(verification_codes)  # Lower index = newer message
                        })
                        break
            
            # If not found in subject, check preview
            if not verification_codes or verification_codes[-1]['code'] != code:
                for pattern in patterns:
                    match = re.search(pattern, preview, re.IGNORECASE)
                    if match:
                        code = match.group(1)
                        if code.isdigit() and len(code) >= 2:  # Any length 2 or more
                            verification_codes.append({
                                'code': code,
                                'subject': message.get('subject', ''),
                                'message_id': message.get('message_id', ''),
                                'from': message.get('from', ''),
                                'index': len(verification_codes)  # Lower index = newer message
                            })
                            break
    
    if verification_codes:
        # Get the most recent code (lowest index)
        latest = verification_codes[0]  # First in list = newest
        print(f"🎉 Found {len(verification_codes)} verification codes:")
        for i, vc in enumerate(verification_codes):
            print(f"   {i+1}. {vc['code']} - {vc['subject']} (from {vc['from']})")
        print(f"✅ Using latest code: {latest['code']}")
        return latest['code']
    
    print("❌ No verification code found")
    return None

if __name__ == "__main__":
    print("🚀 AgentMail API Test")
    print("=" * 40)
    
    # Test getting all messages
    messages = get_messages_from_inbox()
    
    print("\n" + "=" * 40)
    print("🔍 Testing Latest Verification Code:")
    
    # Test getting latest verification code
    code = get_latest_verification_code()
    
    if code:
        print(f"✅ Latest verification code: {code}")
    else:
        print("❌ No verification code found")
