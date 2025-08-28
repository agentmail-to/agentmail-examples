# 🚀 AutoSign - AI Agent Authentication - Built by Het Patel at the YC (YCombinator) AI Agents Hackathon

> **Complete web signup automation with AI-powered CAPTCHA solving and email verification**

AutoSign is an intelligent AI agent that automates the entire signup process across any website. It handles form filling, CAPTCHA solving, email verification, and account creation - all with a single natural language command.

![AutoSign Demo](https://img.shields.io/badge/Status-Ready%20for%20Demo-brightgreen)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![AI Agent](https://img.shields.io/badge/AI%20Agent-Claude%20Sonnet%204-orange)
![Browser-use](https://img.shields.io/badge/Browser--use-v0.6.1+-purple)
![AgentMail](https://img.shields.io/badge/AgentMail-API%20Integration-cyan)

---
Click to watch Demo: Github Sign up + Email Verification using Browser Use and AgentMail
[![Demo Video](https://img.youtube.com/vi/RArk80AVhMg/0.jpg)](https://youtu.be/RArk80AVhMg)

Click to watch Demo: Dev.to Sign up + Captcha Solving with 2Captcha and Agents by Browser Use
[![Captcha Demo](https://img.youtube.com/vi/qFS9Z9Ot-i0/0.jpg)](https://youtu.be/qFS9Z9Ot-i0)


## ✨ What Makes AutoSign Special?

- 🤖 **AI-Powered**: Uses Claude Sonnet 4 for intelligent web automation
- 📧 **Email Integration**: Seamlessly handles email verification with AgentMail
- 🛡️ **CAPTCHA Solving**: Supports 2captcha integration and built-in solving
- 🌐 **Universal**: Works with any website that has signup forms
- 🎯 **Natural Language**: Just describe what you want in plain English
- ⚡ **One Command**: Complete signup automation with a single line

---

## 🎯 Quick Start (5 Minutes)

### 1. Clone & Setup
```bash
# Clone the repository
git clone https://github.com/hetpatel-11/AutoSign.git
cd AutoSign

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install browser-use python-dotenv requests
```

### 2. Get Your API Keys
```bash
# Set up your API keys (you'll get these in the next steps)
export ANTHROPIC_API_KEY="your_anthropic_key"
export AGENTMAIL_API_KEY="your_agentmail_key"
export AGENTMAIL_INBOX_ID="your_email@agentmail.to"
export TWOCAPTCHA_API_KEY="your_2captcha_key"  # Optional
```

### 3. Run Your First Signup
```bash
# Sign up for GitHub
python signup_with_direct_api.py "sign me up for GitHub"

# Create a dev.to account
python signup_with_direct_api.py "create a dev.to account"

# Any custom website
python signup_with_direct_api.py "sign up for https://example.com"
```

---

## 🔑 API Key Setup Guide

### Anthropic API Key (Required)
1. Go to [Anthropic Console](https://console.anthropic.com)
2. Create an account and get your API key
3. Set: `export ANTHROPIC_API_KEY="sk-ant-api03-..."`

### AgentMail Setup (Required)
1. Visit [AgentMail](https://agentmail.to)
2. Create account and get API key
3. Create an inbox (e.g., `myemail@agentmail.to`)
4. Set:
   ```bash
   export AGENTMAIL_API_KEY="your_api_key"
   export AGENTMAIL_INBOX_ID="myemail@agentmail.to"
   ```

### 2captcha Setup (Optional - for CAPTCHA solving)
1. Go to [2captcha.com](https://2captcha.com)
2. Create account and add funds ($3 minimum)
3. Get your API key
4. Set: `export TWOCAPTCHA_API_KEY="your_2captcha_key"`

---

## 🎮 How to Use

### Basic Commands
```bash
# Built-in platforms (tested & working)
python signup_with_direct_api.py "sign me up for GitHub"
python signup_with_direct_api.py "create a dev.to account"
python signup_with_direct_api.py "sign up for Stack Overflow"
python signup_with_direct_api.py "create Reddit account"

# Custom websites
python signup_with_direct_api.py "sign up for https://newsite.com"
python signup_with_direct_api.py "create account on https://example.com"
```

### What Happens Automatically
1. 🤖 **AI Agent** navigates to the signup page
2. 📝 **Form Filling** - enters email, username, password
3. 🛡️ **CAPTCHA Handling** - solves any CAPTCHAs encountered
4. 📧 **Email Verification** - checks AgentMail for verification codes
5. ✅ **Account Creation** - completes the signup process

---

## 🏆 Tested & Working Platforms

| Platform | Features | Status |
|----------|----------|---------|
| **GitHub** | 8-digit verification codes, flexible extraction | ✅ Working |
| **dev.to** | 2captcha integration, third-party CAPTCHA solving | ✅ Working |
| **Stack Overflow** | reCAPTCHA handling, developer platforms | ✅ Working |
| **Reddit** | 6-digit codes, rate limiting handling | ✅ Working |
---

## 🛠️ File Structure

```
AutoSign/
├── signup_with_direct_api.py    # 🎯 MAIN FILE - Run this!
├── simple_agentmail_api.py      # 📧 Email verification system
├── browser_config.py            # 🌐 Browser setup & persistence
├── agentmail_helper.py          # 🛠️ Backup email system
├── test_latest_code.py          # 🧪 Testing email extraction
└── README.md                    # 📖 This file
```

### What Each File Does
- **`signup_with_direct_api.py`** - Main entry point, processes your commands
- **`simple_agentmail_api.py`** - Reads emails and extracts verification codes
- **`browser_config.py`** - Sets up persistent browser sessions
- **`agentmail_helper.py`** - Alternative email handling (backup)
- **`test_latest_code.py`** - Test email extraction functionality

---

## 🎯 Demo Examples

### GitHub Signup
```bash
python signup_with_direct_api.py "sign me up for GitHub"
```
**What it does:**
- Navigates to GitHub signup
- Fills in username, email, password
- Handles 8-digit verification codes
- Completes account creation

### Dev.to with CAPTCHA
```bash
python signup_with_direct_api.py "create a dev.to account"
```
**What it does:**
- Navigates to dev.to signup
- Fills form and encounters reCAPTCHA
- Uses 2captcha to solve CAPTCHA
- Waits 40 seconds for solving
- Completes signup process

### Custom Website
```bash
python signup_with_direct_api.py "sign up for https://newsite.com"
```
**What it does:**
- Navigates to any website
- Automatically detects signup form
- Fills in required fields
- Handles verification if needed

---

## 🔧 Troubleshooting

### Common Issues

**1. API Key Errors**
```bash
# Check your environment variables
echo $ANTHROPIC_API_KEY
echo $AGENTMAIL_API_KEY
echo $AGENTMAIL_INBOX_ID
```

**2. Browser Issues**
```bash
# Clear browser cache
rm -rf ~/.config/browseruse/profiles/persistent
```

**3. Email Verification Issues**
```bash
# Test email extraction
python test_latest_code.py
```

**4. CAPTCHA Not Working**
```bash
# Check 2captcha setup
echo $TWOCAPTCHA_API_KEY
# Make sure you have funds in your 2captcha account
```

### Getting Help
- Check that all API keys are set correctly
- Ensure you have funds in 2captcha (if using CAPTCHA solving)
- Verify your AgentMail inbox is working
- Test with a simple platform like GitHub first

---

## 🚀 Advanced Usage

### Environment Variables File
Create a `.env` file for persistent settings:
```bash
echo "ANTHROPIC_API_KEY=your_key" > .env
echo "AGENTMAIL_API_KEY=your_key" >> .env
echo "AGENTMAIL_INBOX_ID=your_email@agentmail.to" >> .env
echo "TWOCAPTCHA_API_KEY=your_key" >> .env
```

### Custom Website Configuration
Add new websites to `signup_with_direct_api.py`:
```python
'newwebsite': {
    'url': 'https://newwebsite.com/signup',
    'signup_task': 'Go to signup page and create account...',
    'verification_task': 'Handle email verification...'
}
```

---

## 🎉 What AutoSign Demonstrates

### For Hackathons & Demos
- **AI Agent Automation**: Intelligent web interaction
- **API Integration**: Multiple service integrations
- **CAPTCHA Solving**: Advanced security bypass
- **Email Verification**: Complete workflow automation
- **Natural Language**: User-friendly interface
- **Universal Application**: Works with any website

### Technical Features
- **Flexible Code Extraction**: Handles any verification code length
- **Persistent Browser Sessions**: Maintains state across runs
- **Third-party Service Integration**: 2captcha, AgentMail
- **Error Handling**: Robust failure recovery
- **Real-time Monitoring**: Live progress tracking

---

## 🤝 Contributing

Want to add support for more platforms or improve AutoSign?

1. **Test new platforms** and add configurations
2. **Improve CAPTCHA handling** for different types
3. **Add more email providers** beyond AgentMail
4. **Enhance error handling** and recovery
5. **Create better documentation** and examples

---

## 📄 License

This project is open source and available under the MIT License.

---

## 🎯 Ready to Try?

```bash
# Get started in 5 minutes!
git clone https://github.com/hetpatel-11/AutoSign.git
cd AutoSign
python -m venv .venv
source .venv/bin/activate
pip install browser-use python-dotenv requests

# Set your API keys and run!
python signup_with_direct_api.py "sign me up for GitHub"
```

**AutoSign: Authentication for computers using agents** 🚀

---

*Built with ❤️ for the AI automation community*
