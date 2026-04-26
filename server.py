from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import asyncio
import edge_tts
import threading
import uuid
import re
import os
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

import pygame

# =====================================================
# 🚀 APP
# =====================================================
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def home():
    return FileResponse("static/index.html")


# =====================================================
# 🌐 STATE
# =====================================================
clients = set()

STATE = {
    "running": True,
    "voice_enabled": True,
    "voice": "en-GB-RyanNeural",
}

event_queue = asyncio.Queue()

ACTIVE_MATCH = {
    "url": None,
    "driver": None,
    "task": None,
    "running": False
}


# =====================================================
# 🔊 INIT AUDIO ENGINE (FIX FOR WINDOWS)
# =====================================================
pygame.mixer.init()


def play_audio(file):
    try:
        pygame.mixer.music.load(file)
        pygame.mixer.music.play()
    except Exception as e:
        print("AUDIO ERROR:", e)


# =====================================================
# 🧠 DIRECTOR AI
# =====================================================
def director_ai(text: str):
    t = text.upper()

    if "OUT" in t:
        return "🚨 WICKET! HUGE BREAKTHROUGH!"
    if "SIX" in t:
        return "🔥 SIX! OUT OF THE GROUND!"
    if "FOUR" in t:
        return "⚡ FOUR RUNS!"
    if "50" in t:
        return "🏏 HALF CENTURY!"
    if "WIDE" in t:
        return "⚠️ WIDE BALL!"
    if "NO BALL" in t:
        return "🚨 NO BALL! FREE HIT!"
    return text


# =====================================================
# 📡 BROADCAST
# =====================================================
async def broadcast(msg):
    dead = set()

    for c in clients:
        try:
            await c.send_text(msg)
        except:
            dead.add(c)

    clients.difference_update(dead)


# =====================================================
# 🔊 TTS (EDGE TTS FIXED)
# =====================================================
async def speak(text):
    if not STATE["voice_enabled"]:
        return

    try:
        file = f"C:/cricket_voices/{uuid.uuid4().hex}.mp3"

        comm = edge_tts.Communicate(
            text=text,
            voice=STATE["voice"],
            rate="+10%"
        )

        await comm.save(file)

        play_audio(file)

    except Exception as e:
        print("TTS ERROR:", e)


# =====================================================
# 🕷️ DRIVER CREATOR (ROBUST)
# =====================================================
def create_driver(url):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)

    driver.get(url)
    return driver


# =====================================================
# 🔁 SAFE SCRAPER LOOP (CRASH PROOF)
# =====================================================
async def scraper_loop():
    seen = set()

    while ACTIVE_MATCH["running"]:
        try:
            driver = ACTIVE_MATCH["driver"]

            if not driver:
                await asyncio.sleep(1)
                continue

            blocks = driver.find_elements(By.CLASS_NAME, "cm-b-comment-c2")

            for b in blocks[::-1]:
                text = b.text.strip()

                if not text:
                    continue

                key = hash(text)

                if key in seen:
                    continue

                seen.add(key)

                final = director_ai(text)

                await event_queue.put(final)

        except Exception as e:
            print("SCRAPER ERROR:", e)

            # 🔥 AUTO RECOVERY (IMPORTANT FIX)
            try:
                if ACTIVE_MATCH["url"]:
                    print("♻️ Restarting driver...")
                    ACTIVE_MATCH["driver"] = create_driver(ACTIVE_MATCH["url"])
            except:
                pass

        await asyncio.sleep(1)


# =====================================================
# 🎯 EVENT WORKER
# =====================================================
async def event_worker():
    while True:
        text = await event_queue.get()

        print("LIVE:", text)

        await broadcast(text)

        asyncio.create_task(speak(text))


# =====================================================
# 🏟️ START MATCH (FORCE FIXED)
# =====================================================
def start_match(url: str):
    url = url.strip()

    if not re.match(r"^https?://", url):
        print("❌ INVALID URL")
        return

    print("🏟️ START MATCH:", url)

    ACTIVE_MATCH["running"] = False

    time.sleep(1)

    if ACTIVE_MATCH["driver"]:
        try:
            ACTIVE_MATCH["driver"].quit()
        except:
            pass

    driver = create_driver(url)

    ACTIVE_MATCH["url"] = url
    ACTIVE_MATCH["driver"] = driver
    ACTIVE_MATCH["running"] = True

    ACTIVE_MATCH["task"] = asyncio.create_task(scraper_loop())


# =====================================================
# 📡 WS CONTROL
# =====================================================
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)

    try:
        while True:
            data = await websocket.receive_text()

            print("CMD:", data)

            if data == "start":
                STATE["running"] = True

            elif data == "stop":
                STATE["running"] = False

            elif data == "mute":
                STATE["voice_enabled"] = False

            elif data == "unmute":
                STATE["voice_enabled"] = True

            elif data.startswith("match:") or data.startswith("force:"):
                url = data.split(":", 1)[1].strip()
                start_match(url)
                await websocket.send_text("🏟️ MATCH STARTED")

    except WebSocketDisconnect:
        clients.remove(websocket)


# =====================================================
# 🚀 STARTUP
# =====================================================
@app.on_event("startup")
async def startup():
    asyncio.create_task(event_worker())
    print("🚀 ESPN AUTOPILOT SYSTEM READY")