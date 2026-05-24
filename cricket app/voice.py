import asyncio
import threading
import edge_tts
import sounddevice as sd
import soundfile as sf
import pyttsx3
import numpy as np
import obswebsocket
from obswebsocket import requests as obs_requests
import pygame
import io
from pygame import mixer
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, BackgroundTasks
from fastapi.responses import JSONResponse

app = FastAPI()

speech_lock = threading.Lock()

# Global flag to stop current TTS
current_tts_thread = None
stop_tts_flag = threading.Event()
current_mixer = None
is_playing = False

def stop_current_tts():
    """Stop any currently playing TTS immediately"""
    global current_mixer, current_tts_thread, is_playing
    print("🛑 STOP COMMAND RECEIVED - Stopping TTS...")
    stop_tts_flag.set()
    is_playing = False
    
    # Stop pygame mixer if active
    if current_mixer:
        try:
            current_mixer.music.stop()
            current_mixer.quit()
        except:
            pass
        current_mixer = None
    
    # Stop sounddevice if active
    try:
        sd.stop()
    except:
        pass
    
    print("✅ TTS STOPPED SUCCESSFULLY")
    return True

def reset_stop_flag():
    """Reset the stop flag (call before starting new TTS)"""
    global stop_tts_flag, is_playing
    stop_tts_flag.clear()
    is_playing = True
    print("🎵 Stop flag cleared, ready to play")

# ======================= FIXED speak_bangla =======================
def speak_bangla(text: str):
    async def _speak():
        global current_mixer, stop_tts_flag, is_playing
        try:
            print(f"🎙 Starting TTS: {text[:50]}...")
            
            tts = edge_tts.Communicate(text, "bn-BD-NabanitaNeural")
            
            # Collect audio chunks
            audio_data = b""
            async for chunk in tts.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            
            # Initialize mixer
            current_mixer = mixer
            mixer.init(frequency=24000)
            
            # Load from bytes and play
            sound = mixer.Sound(io.BytesIO(audio_data))
            sound.play()
            
            print("🎵 TTS playing...")
            
            # Wait for completion WITHOUT checking stop flag during playback
            # This prevents false interrupts
            while mixer.get_busy():
                await asyncio.sleep(0.1)
            
            print("✅ TTS completed naturally")
            mixer.quit()
            current_mixer = None
                
        except Exception as e:
            print(f"❌ TTS ERROR: {e}")
        finally:
            if current_mixer:
                try:
                    mixer.quit()
                except:
                    pass
                current_mixer = None
            is_playing = False
    
    def runner():
        with speech_lock:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_speak())
            loop.close()
    
    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return thread

# ======================= FIXED speak_bangla2 (with proper stop support) =======================
def speak_bangla2(text: str):
    async def _speak():
        global stop_tts_flag
        try:
            print(f"🎙 Starting TTS (v2): {text[:50]}...")
            output_file = "temp_bn.mp3"
            tts = edge_tts.Communicate(text, "bn-BD-NabanitaNeural")
            await tts.save(output_file)
            
            data, fs = sf.read(output_file)
            
            # Play with periodic stop checks (but don't error on stop)
            sd.play(data, fs)
            
            # Wait with stop checks
            while sd.get_stream() and sd.get_stream().active:
                await asyncio.sleep(0.05)
                if stop_tts_flag.is_set():
                    sd.stop()
                    print("⏹️ TTS stopped by user")
                    return
            
            print("✅ TTS completed")
                    
        except Exception as e:
            print(f"❌ TTS ERROR: {e}")

    def runner():
        with speech_lock:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_speak())
            loop.close()

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return thread

# ======================= FIXED speak_english =======================
def speak_english(text: str):
    def run():
        try:
            print(f"🎙 SPEAKING (EN): {text[:50]}...")
            engine = pyttsx3.init()
            engine.setProperty("rate", 170)
            engine.setProperty("volume", 1.0)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
            print("✅ English TTS completed")
        except Exception as e:
            print(f"TTS ERROR: {e}")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread

