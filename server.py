import asyncio
import tempfile
import threading
import queue
import json
import os
from collections import deque

from google import genai
import websockets
import mlx_whisper
from silero_vad import load_silero_vad, read_audio, get_speech_timestamps
from pydantic import BaseModel

vad_model = load_silero_vad()
transcript_queue = queue.Queue()
clients = set()
llmClient = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

class AssistantOutput(BaseModel):
    response: str
    task: str

# Create an event loop for the background thread
async def process_queue():
    while True:
        try:
            # Get text from queue with a timeout to allow checking for thread exit
            try:
                text = transcript_queue.get(timeout=1)
            except queue.Empty:
                await asyncio.sleep(0.1)  # Prevent busy-waiting
                continue

            context = "\n".join(CONTEXT_WINDOW)
            if text:
                # TODO make it respond to "jarvis" more often(?)
                # TODO give it prior context (maybe)
                prompt = f"""
                Your name is JARVIS. You are a helpful virtual assistant.

                Analyze the following input. It is from a person speaking.
                They are speaking to themselves. They may occasionally ask you something; when they do, they will always call you by name.

                If the user asks you something, respond succinctly (2 sentences max), populating the "response" json field.
                Alternatively, if the user notes something to themselves that can be construed as a task, summarize it and populate the "task" field in your response.
                Otherwise, return both fields empty.
                It is very important that you only fill in one of the fields when you are absolutely certain you should, because doing so unnecessarily will break the user's thought process.

                For responses, know your limitations: you should only return a sentence or two at most.
                If the user's request would take more than a couple of short sentences to fulfill, assume that it was not meant for you and output an empty string.
                You should not try to be interactive, so do not ask the user for a follow up.

                The input: {text}
                """

                response = llmClient.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=prompt,
                    config={
                        'response_mime_type': 'application/json',
                        'response_schema': AssistantOutput
                    }
                )
                response_json = json.loads(response.text)
                output = response_json['response']
                llm_message = json.dumps({
                    "type": "llm",
                    "data": output
                })
                print(output)
                print(response_json['task'])

                # Create tasks for sending to all clients
                send_tasks = []
                for ws in clients:
                    send_tasks.append(asyncio.create_task(ws.send(llm_message)))

                # Wait for all send operations to complete
                if send_tasks:
                    await asyncio.gather(*send_tasks)

        except Exception as e:
            print(f"Error in process_queue: {e}")
            await asyncio.sleep(1)  # Prevent rapid error loops

def run_async_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

# Start background thread with its own event loop
def start_background_thread():
    loop = asyncio.new_event_loop()
    threading.Thread(target=run_async_loop, args=(loop,), daemon=True).start()
    asyncio.run_coroutine_threadsafe(process_queue(), loop)

# Context retention: Keep last N lines
CONTEXT_WINDOW = deque(maxlen=10)

async def transcribe_audio(websocket):
    clients.add(websocket)
    try:
        async for message in websocket:
            print("Receiving audio...")

            with tempfile.NamedTemporaryFile(suffix='.webm') as file:
                file.write(message)

                audio = read_audio(file.name)
                speech_timestamps = get_speech_timestamps(audio, vad_model)

                if speech_timestamps:
                    result = mlx_whisper.transcribe(
                        file.name,
                        language='en',
                        path_or_hf_repo="/Users/tm/models/mlx/whisper-large-v3-mlx",
                        initial_prompt="You are a digital assistant named JARVIS"
                    )

                    transcript_queue.put(result['text'])
                    # FIXME tries to send too many bytes over WS somewhere (see screenshot)
                    await websocket.send(json.dumps({
                        "type": "transcript",
                        "data": result['text']
                    }))
                else:
                    print("No speech detected")
                    await websocket.send(json.dumps({
                        "type": "transcript",
                        "data": ""
                    }))
    finally:
        clients.remove(websocket)

async def main():
    # Start the background processing thread
    start_background_thread()

    server = await websockets.serve(transcribe_audio, "0.0.0.0", 8765)
    print("Listening...")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())