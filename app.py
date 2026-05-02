from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import asyncio
import threading
import time
import json

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
    "url": None,
    "match_id": None
}

MAIN_LOOP = None
worker_thread = None

# replay buffer (for frontend replay engine)
REPLAY_BUFFER = []


# =========================================
# 📡 BROADCAST SYSTEM
# =========================================
async def broadcast(payload: dict):
    dead = set()

    msg = json.dumps(payload)

    for ws in clients:
        try:
            await ws.send_text(msg)
        except:
            dead.add(ws)

    clients.difference_update(dead)


def send(payload: dict):
    """Thread-safe broadcaster"""
    if MAIN_LOOP:
        asyncio.run_coroutine_threadsafe(
            broadcast(payload),
            MAIN_LOOP
        )


# =========================================
# 🎙 OUTPUT HOOK (VERY IMPORTANT)
# =========================================
def emit_commentary(text: str):
    print("🎙", text)

    # store for replay
    REPLAY_BUFFER.append(text)
    if len(REPLAY_BUFFER) > 30:
        REPLAY_BUFFER.pop(0)

    send({
        "type": "commentary",
        "data": text
    })


def emit_score(score="0/0", overs="0.0"):
    send({
        "type": "score",
        "data": {
            "score": score,
            "overs": overs
        }
    })


def emit_system(text):
    send({
        "type": "system",
        "data": text
    })


# =========================================
# 🧠 AI ENGINE WRAPPER (THREAD SAFE FIX)
# =========================================
def run_ai_engine(url: str):
    try:
        print("🚀 AI ENGINE START:", url)

        STATE["running"] = True

        # ---------------------------------
        # 🔥 IMPORTANT HOOK
        # ---------------------------------
        # You must modify ai_commentry() to call:
        # emit_commentary(...)
        # emit_score(...)
        # ---------------------------------

        ai_commentry(url)

    except Exception as e:
        print("❌ AI ERROR:", e)

    finally:
        STATE["running"] = False
        emit_system("🛑 Match Engine Stopped")
        print("🛑 AI ENGINE STOPPED")


# =========================================
# 🏟 START MATCH
# =========================================
def start_match(url: str):
    global worker_thread

    print("🔥 START MATCH:", url)

    # stop previous safely
    STATE["running"] = False
    time.sleep(1)

    if worker_thread and worker_thread.is_alive():
        print("⚠️ Previous engine still running, ignoring new start")
        return

    STATE["url"] = url
    STATE["running"] = True

    emit_system("🚀 Match Started")

    worker_thread = threading.Thread(
        target=run_ai_engine,
        args=(url,),
        daemon=True
    )
    worker_thread.start()

    print("✅ ENGINE THREAD STARTED")


# =========================================
# 🛑 STOP MATCH
# =========================================
def stop_match():
    print("🛑 STOP REQUEST")

    STATE["running"] = False
    emit_system("🛑 Match Stopped")


# =========================================
# 🌐 WEBSOCKET CONTROL ROOM
# =========================================
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    global MAIN_LOOP

    await ws.accept()
    clients.add(ws)

    print("🟢 CLIENT CONNECTED")

    try:
        while True:
            raw = await ws.receive_text()
            print("📩 WS:", raw)

            msg = None
            try:
                msg = json.loads(raw)
            except:
                pass

            # =========================
            # JSON MODE (PRIMARY)
            # =========================
            if isinstance(msg, dict):

                action = msg.get("type")
                data = msg.get("data")

                if action in ["start", "force"] and data:
                    start_match(data)

                elif action == "stop":
                    stop_match()

                elif action == "replay":
                    send({
                        "type": "replay",
                        "data": REPLAY_BUFFER
                    })

                elif action == "mute":
                    STATE["voice"] = False

                elif action == "unmute":
                    STATE["voice"] = True

                elif action == "status":
                    send({
                        "type": "status",
                        "data": STATE
                    })

            # =========================
            # FALLBACK STRING MODE
            # =========================
            else:

                if raw.startswith("start:") or raw.startswith("force:"):
                    url = raw.split(":", 1)[1]
                    start_match(url)

                elif raw == "stop":
                    stop_match()

                elif raw == "replay":
                    send({
                        "type": "replay",
                        "data": REPLAY_BUFFER
                    })

    except WebSocketDisconnect:
        clients.remove(ws)
        print("🔴 CLIENT DISCONNECTED")


# =========================================
# 🚀 STARTUP
# =========================================
@app.on_event("startup")
async def startup():
    global MAIN_LOOP

    MAIN_LOOP = asyncio.get_running_loop()
    print("🏏 IPL BROADCAST ENGINE ONLINE")