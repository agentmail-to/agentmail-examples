# Crosspost Plan: Voice to Email

## Show HN Post

**Title:** Show HN: Dictate emails by voice, send them from an AI agent's inbox

**Body:**
A Python tool that records your voice, transcribes with Whisper, cleans up the text with GPT-4o-mini, and sends it as an email via AgentMail (https://agentmail.to).

Useful for hands-free email, accessibility, or when typing is not practical.

The agent creates its own inbox, so you are sending from a dedicated address rather than your personal email.

Repo: https://github.com/agentmail-to/voice-to-email

---

## Dev.to Article

**Title:** Build a Voice-to-Email Agent with Whisper and AgentMail

**Tags:** python, ai, accessibility, voice

---

Voice is faster than typing for most people. This tutorial builds a tool that lets you dictate emails and send them instantly.

### Pipeline

1. Record audio (microphone or file)
2. Transcribe with OpenAI Whisper
3. Clean up with GPT-4o-mini (grammar, filler words, formatting)
4. Send via AgentMail

Full code: [github.com/agentmail-to/voice-to-email](https://github.com/agentmail-to/voice-to-email)

---

## X Thread (5 tweets)

**Tweet 1:**
Built a voice-to-email agent. Dictate, transcribe, clean up, send. All from the command line.

**Tweet 2:**
Pipeline: mic input -> Whisper transcription -> GPT-4o-mini cleanup -> AgentMail send.

Filler words removed, grammar fixed, professional formatting applied.

**Tweet 3:**
The agent has its own inbox via @AgentMailTo. Recipients see a real reply-to address.

**Tweet 4:**
Fallback mode: if no mic is available, type your message. The cleanup step still runs.

**Tweet 5:**
Repo: github.com/agentmail-to/voice-to-email

pip install agentmail openai sounddevice numpy scipy
