import asyncio
import websockets
import pyaudio

# Audio Stream Config
CHUNK = 1600  # 100ms at 16kHz
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

async def send_audio():
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

    async with websockets.connect("ws://10.35.20.13:8765") as websocket:
        print("Streaming audio...")
        while True:
            data = stream.read(CHUNK)
            await websocket.send(data)

asyncio.run(send_audio())