import os
import json
import tempfile

from agentmail import AgentMail
from openai import OpenAI

agentmail = AgentMail(api_key=os.environ["AGENTMAIL_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

try:
    import sounddevice as sd
    import numpy as np
    from scipy.io.wavfile import write as write_wav
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

SAMPLE_RATE = 16000
RECORD_SECONDS = 30

CLEANUP_PROMPT = """Clean up this voice transcription into a proper email body.
Fix grammar, remove filler words, and format it as a professional email.
Do not add a greeting or sign-off unless the speaker included one.
Return only the cleaned email text.

Transcription: {text}"""


def record_audio(duration: int = RECORD_SECONDS) -> str:
    if not AUDIO_AVAILABLE:
        print("Audio libraries not installed. Install with: pip install sounddevice numpy scipy")
        return input("Type your message instead: ")

    print(f"Recording for up to {duration} seconds. Press Ctrl+C to stop early.")
    try:
        audio = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
        sd.wait()
    except KeyboardInterrupt:
        sd.stop()
        audio = sd.rec(0, samplerate=SAMPLE_RATE, channels=1, dtype="int16")

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    write_wav(tmp.name, SAMPLE_RATE, audio)
    return tmp.name


def transcribe(audio_path: str) -> str:
    with open(audio_path, "rb") as f:
        result = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
        )
    return result.text


def clean_up_email(raw_text: str) -> str:
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": CLEANUP_PROMPT.format(text=raw_text)}],
    )
    return resp.choices[0].message.content


def get_input(prompt: str) -> str:
    if AUDIO_AVAILABLE:
        print(prompt)
        audio_path = record_audio(duration=10)
        if audio_path.endswith(".wav"):
            text = transcribe(audio_path)
            os.unlink(audio_path)
        else:
            text = audio_path
        print(f"  Heard: {text}")
        return text
    else:
        return input(prompt + " ")


def main():
    inbox = agentmail.inboxes.create(display_name="Voice Email Agent")
    print(f"Created inbox: {inbox.email}\n")

    while True:
        print("=== New Email ===")
        to_address = get_input("Say the recipient's email address:")
        subject = get_input("Say the subject:")

        print("Dictate your email body:")
        audio_path = record_audio()
        if audio_path.endswith(".wav"):
            raw = transcribe(audio_path)
            os.unlink(audio_path)
        else:
            raw = audio_path

        print(f"\nRaw transcription: {raw}")
        cleaned = clean_up_email(raw)
        print(f"\nCleaned email:\n{cleaned}\n")

        confirm = input("Send this email? (y/n): ").strip().lower()
        if confirm == "y":
            msg = agentmail.messages.send(
                inbox_id=inbox.id,
                to=[to_address.strip()],
                subject=subject.strip(),
                text=cleaned,
            )
            print(f"Sent! Message ID: {msg.id}\n")
        else:
            print("Cancelled.\n")

        if input("Send another? (y/n): ").strip().lower() != "y":
            break

    print("Done.")


if __name__ == "__main__":
    main()
