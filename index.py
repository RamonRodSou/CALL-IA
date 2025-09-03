from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI
from dotenv import load_dotenv
import time
import os

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")

print("id", OPENAI_ASSISTANT_ID)
print("key", OPENAI_API_KEY)

client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)

threads = {}

@app.route("/voice", methods=["POST"])
def voice():
    call_sid = request.form.get("CallSid")
    twiml = VoiceResponse()

    thread = client.beta.threads.create()
    threads[call_sid] = thread.id

    twiml.say("Hello! How can I help you today?", voice="Polly.Joanna")
    twiml.gather(input="speech", timeout=5, speech_timeout="auto", action="/process-speech", method="POST")

    return Response(str(twiml), mimetype="text/xml")

@app.route("/process-speech", methods=["POST"])
def process_speech():
    call_sid = request.form.get("CallSid")
    user_text = request.form.get("SpeechResult")
    twiml = VoiceResponse()

    thread_id = threads.get(call_sid)
    if not thread_id:
        twiml.say("Sorry, we could not find your session.")
        twiml.hangup()
        return Response(str(twiml), mimetype="text/xml")

    client.beta.threads.messages.create(
        thread_id,
        role="user",
        content=user_text
    )

    run = client.beta.threads.runs.create(
        thread_id,
        assistant_id=OPENAI_ASSISTANT_ID
    )

    result = None
    retries = 0
    while retries < 20:
        time.sleep(0.1)
        result = client.beta.threads.runs.retrieve(run.id, thread_id=thread_id)

        if result.status == "completed":
            break
        retries += 1

    if result.status != "completed":
        twiml.say("Sorry, the AI did not complete the response.")
        twiml.hangup()
        return Response(str(twiml), mimetype="text/xml")

    messages = client.beta.threads.messages.list(thread_id)
    reply_msg = next((m for m in messages.data if m.role == "assistant"), None)
    reply = reply_msg.content[0].text.value.strip() if reply_msg else ""

    if reply:
        twiml.say(reply, voice="alice")
        if "goodbye" not in reply.lower():
            twiml.gather(input="speech", timeout=5, speech_timeout="auto", action="/process-speech", method="POST")
        else:
            twiml.hangup()

    return Response(str(twiml), mimetype="text/xml")

if __name__ == "__main__":
    app.run(port=4000)
