from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import threading
import asyncio

from run_old import ai_commentry

# =========================================
# 🚀 APP INIT
# =========================================
app = FastAPI()
app.mount("/static", StaticFiles(directory="templates"), name="static")


@app.get("/")
def home():
    return FileResponse("templates/index.html")


# =========================================
# 🌐 GLOBAL STATE
# =========================================
clients = set()

STATE = {
    "running": False,
    "voice": True,
    "url": None
}

# =========================================
# 📡 BROADCAST SYSTEM
# =========================================
async def broadcast(msg: str):
    dead = set()

    for ws in clients:
        try:
            await ws.send_text(msg)
        except:
            dead.add(ws)

    clients.difference_update(dead)


# =========================================
# 🔊 TTS HOOK
# =========================================
def speak(text: str):
    if STATE["voice"]:
        print("🎙", text)


# =========================================
# 🧠 RUN AI COMMENTARY IN BACKGROUND THREAD
# =========================================
def run_ai_engine(url: str):
    """
    IMPORTANT:
    Runs your Playwright + scraping engine safely in background thread.
    """
    try:
        print(f"🚀 AI ENGINE STARTED WITH URL: {url}")
        ai_commentry(url)   # 🔥 YOUR EXISTING CODE (UNCHANGED)
    except Exception as e:
        print("❌ AI ENGINE ERROR:", e)


def start_match(url: str):
    """
    This is now NON-BLOCKING.
    """
    print("🏏 START MATCH REQUEST:", url)

    STATE["running"] = True
    STATE["url"] = url

    # 🚀 RUN AI IN SEPARATE THREAD
    thread = threading.Thread(
        target=run_ai_engine,
        args=(url,),
        daemon=True
    )
    thread.start()

    print("✅ MATCH ENGINE LAUNCHED (NON-BLOCKING)")


def stop_match():
    print("🛑 STOP MATCH")

    STATE["running"] = False
    STATE["url"] = None


# =========================================
# 🌐 WEBSOCKET CONTROL ROOM
# =========================================
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)

    print("🟢 CLIENT CONNECTED")

    try:
        while True:
            data = await ws.receive_text()
            print("📩 WS:", data)

            # =========================
            # FORCE START (MAIN FIX)
            # =========================
            if data.startswith("force:"):
                url = data.split(":", 1)[1].strip()

                if not url:
                    await ws.send_text("❌ INVALID URL")
                    continue

                print("🔥 FORCE START RECEIVED:", url)

                start_match(url)

                await ws.send_text(f"🚀 MATCH STARTED: {url}")

            # =========================
            # STOP
            # =========================
            elif data == "stop":
                stop_match()
                await ws.send_text("🛑 STOPPED")

            # =========================
            # MUTE
            # =========================
            elif data == "mute":
                STATE["voice"] = False
                await ws.send_text("🔇 MUTED")

            # =========================
            # UNMUTE
            # =========================
            elif data == "unmute":
                STATE["voice"] = True
                await ws.send_text("🔊 UNMUTED")

            # =========================
            # STATUS
            # =========================
            elif data == "status":
                await ws.send_text(
                    f"📊 RUNNING: {STATE['running']} | URL: {STATE['url']}"
                )

    except WebSocketDisconnect:
        clients.remove(ws)
        print("🔴 CLIENT DISCONNECTED")


# =========================================
# 🚀 STARTUP
# =========================================
@app.on_event("startup")
async def startup():
    print("🏏 IPL BROADCAST CONTROL ROOM ONLINE")