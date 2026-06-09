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
import time
import tempfile
import os

speech_lock = threading.Lock()

# Global flag to stop current TTS
current_tts_thread = None
stop_tts_flag = threading.Event()
current_mixer = None
is_playing = False
last_play_time = 0

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

# ======================= FIXED speak_bangla (with device check) =======================
def speak_bangla(text: str):
    async def _speak():
        global current_mixer, stop_tts_flag, is_playing, last_play_time
        try:
            # Ensure previous playback is cleaned up
            await asyncio.sleep(0.1)
            
            print(f"🎙 Starting TTS: {text[:50]}...")
            
            tts = edge_tts.Communicate(text, "bn-BD-NabanitaNeural")
            
            # Collect audio chunks
            audio_data = b""
            async for chunk in tts.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_data)
                temp_file = f.name
            
            try:
                # Use sounddevice which is more reliable than pygame
                data, fs = sf.read(temp_file)
                
                # Play audio
                sd.play(data, fs)
                print("🎵 TTS playing...")
                
                # Wait for completion with stop checks
                while sd.get_stream() and sd.get_stream().active:
                    await asyncio.sleep(0.1)
                    if stop_tts_flag.is_set():
                        sd.stop()
                        print("⏹️ TTS stopped by user")
                        return
                
                print("✅ TTS completed naturally")
                
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_file)
                except:
                    pass
                
        except Exception as e:
            print(f"❌ TTS ERROR: {e}")
        finally:
            is_playing = False
    
    def runner():
        with speech_lock:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_speak())
            loop.close()
    
    # Stop any existing TTS before starting new one
    #stop_current_tts()
    time.sleep(0.1)  # Small delay to ensure cleanup
    reset_stop_flag()
    
    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return thread


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

