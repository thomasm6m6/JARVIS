import asyncio
import websockets
import whisper
import io
import soundfile as sf
from collections import deque
import numpy as np
from scipy.signal import resample_poly

import queue
import ollama
import threading

# Load Whisper Model
model = whisper.load_model("base")

transcript_queue = queue.Queue()

# Function to process text and extract tasks
def extract_tasks():
    while True:
        text = transcript_queue.get()  # Get transcribed text
        if text:
            prompt = f"""
            Extract all actionable tasks from this live transcript. 
            Example: 
            "I need to email Alex by Friday and finish my report ASAP."
            Output:
            [
                {{"task": "Email Alex", "deadline": "Friday", "priority": "medium"}},
                {{"task": "Finish my report", "deadline": "ASAP", "priority": "high"}}
            ]

            Input: {text}
            """
            response = ollama.chat(model="llama3.1", messages=[{"role": "user", "content": prompt}])
            print(response["message"]["content"])  # Send tasks to database or UI

# Start background thread to process text
threading.Thread(target=extract_tasks, daemon=True).start()

# Context retention: Keep last N sentences
CONTEXT_WINDOW = deque(maxlen=5)

# Audio buffer (to accumulate ~5-10s before transcribing)
# BUFFER_DURATION = 5  # Seconds
# SAMPLE_RATE = 16000  # Target sample rate for Whisper
# BYTES_PER_SAMPLE = 2  # int16 = 2 bytes per sample
# CHANNELS = 1  # Mono audio

# Calculate required buffer size
# BUFFER_SIZE = BUFFER_DURATION * SAMPLE_RATE * BYTES_PER_SAMPLE * CHANNELS

async def transcribe_audio(websocket):
    print("Client connected, receiving audio...")

    accumulated_audio = b""

    async for message in websocket:
        accumulated_audio += message  # Collect small chunks

        # Process when we have enough audio
        if len(accumulated_audio) > 32000:  # ~1 sec at 16kHz
            # print(f"Processing {BUFFER_DURATION}s of audio...")

            audio_array = np.frombuffer(accumulated_audio, dtype=np.int16).astype(np.float32) / 32768.0

            # if SAMPLE_RATE != 16000:
            #     audio_array = resample_poly(audio_array, 16000, SAMPLE_RATE)

            # audio_data = io.BytesIO(accumulated_audio)
            # audio, samplerate = sf.read(audio_data, dtype='int16')

            # Transcribe
            result = model.transcribe(audio_array, fp16=False)
            transcript = result["text"]

            # Store in context window
            CONTEXT_WINDOW.append(transcript)

            # Combine for full context-aware processing
            full_context = " ".join(CONTEXT_WINDOW)
            print("Context-Aware Transcript:", full_context)

            # TODO: Process tasks using LLM
            # process_transcription(full_context)
            transcript_queue.put(full_context)

            accumulated_audio = b""  # Reset buffer

async def main():
    # Start WebSocket Server
    start_server = websockets.serve(transcribe_audio, "0.0.0.0", 8765)
    await start_server
    print("Websocket server hopefully running...")
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
# asyncio.get_event_loop().run_until_complete(start_server)
# asyncio.get_event_loop().run_forever()