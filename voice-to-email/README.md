# Voice to Email Agent

An AI agent that takes voice input via microphone, transcribes it, and sends it as an email through AgentMail. Built with AgentMail, OpenAI Whisper, and GPT-4o-mini.

## What It Does

- Records audio from your microphone
- Transcribes speech to text with OpenAI Whisper
- Cleans up the transcription into a proper email with GPT-4o-mini
- Sends the email from a dedicated AgentMail inbox
- Supports "reply" mode to respond to existing threads by voice

![Demo](assets/demo.gif)

## Why This Exists

Voice is faster than typing for longer emails. This agent bridges voice input to email output, useful for hands-free environments, accessibility, or when you want to dictate emails to an AI that sends them on your behalf.

## Prerequisites

- Python 3.10+
- [AgentMail](https://agentmail.to) API key
- [OpenAI](https://platform.openai.com) API key
- A working microphone

## Install

```bash
git clone https://github.com/agentmail-to/voice-to-email.git
cd voice-to-email
pip install -r requirements.txt
cp .env.example .env
```

## Quickstart

```bash
python src/main.py
```

The agent will prompt you to:
1. Speak the recipient's email address
2. Speak the subject
3. Dictate the email body
4. Confirm and send

## How to Deploy

This is a local tool, not a server. Run it on any machine with a microphone.

## Docs

- [AgentMail Python SDK](https://docs.agentmail.to/sdks/python)
- [Sending Messages](https://docs.agentmail.to/api-reference/messages/send-message)

## License

MIT
