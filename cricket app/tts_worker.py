# tts_worker.py
import pyttsx3
import asyncio
#from commentary_engine import get_commentary

engine = pyttsx3.init()
engine.setProperty('rate', 165)
engine.setProperty('volume', 1.0)

def speak(text):
    engine.say(text)
    engine.runAndWait()

async def tts_loop():
    while True:
        text = "Hello World"#await get_commentary()
        await asyncio.to_thread(speak, text)