import asyncio
import threading
import edge_tts
import sounddevice as sd
import soundfile as sf
import pyttsx3
import threading
import asyncio
import numpy as np
import sounddevice as sd
import obswebsocket
from obswebsocket import requests as obs_requests
import threading
import asyncio
import edge_tts
import pygame
import io
from pygame import mixer

speech_lock = threading.Lock()

def speak_bangla(text: str):
    async def _speak():
        try:
            print("🎙 AI SPEAK (BN):", text)
            
            tts = edge_tts.Communicate(text, "bn-BD-NabanitaNeural")
            
            # Collect audio chunks
            audio_data = b""
            async for chunk in tts.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            
            # Initialize mixer
            mixer.init(frequency=24000)  # edge_tts default sample rate
            
            # Load from bytes and play
            sound = mixer.Sound(io.BytesIO(audio_data))
            sound.play()
            
            # Wait for completion
            while mixer.get_busy():
                await asyncio.sleep(0.01)
            
            mixer.quit()
                
        except Exception as e:
            print("❌ TTS ERROR:", e)
    
    def runner():
        with speech_lock:
            asyncio.run(_speak())
    
    threading.Thread(target=runner, daemon=True).start()
def speak_bangla2(text: str):

    async def _speak():

        try:
            print("🎙 AI SPEAK (BN):", text)

            output_file = "temp_bn.mp3"

            tts = edge_tts.Communicate(
                text,
                "bn-BD-NabanitaNeural"
            )

            await tts.save(output_file)

            data, fs = sf.read(output_file)

            sd.play(data, fs)
            sd.wait()

        except Exception as e:
            print("❌ TTS ERROR:", e)

    def runner():
        with speech_lock:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_speak())
            loop.close()

    threading.Thread(
        target=runner,
        daemon=True
    ).start()

def speak_english(text: str):
    def run():
        with speech_lock:
            try:
                print("🎙 SPEAKING:", text)

                engine = pyttsx3.init()   # 🔥 NEW ENGINE EVERY TIME
                engine.setProperty("rate", 170)
                engine.setProperty("volume", 1.0)                

                engine.say(text)
                engine.runAndWait()

            except Exception as e:
                print("TTS ERROR:", e)

    threading.Thread(target=run, daemon=True).start()
