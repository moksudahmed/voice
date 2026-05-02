from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio

from state import MATCH
from ws_manager import clients
from engine import engine

app = FastAPI()

# ✅ STATIC FILES
app.mount("/static", StaticFiles(directory="static"), name="static")

# ✅ TEMPLATES (FIXED)
templates = Jinja2Templates(directory="templates")
templates.env.cache = {}  # 🔥 prevent Jinja bug


# =========================
# START ENGINE
# =========================
@app.on_event("startup")
async def startup():
    asyncio.create_task(engine())
    print("🚀 ENGINE RUNNING")


# =========================
# ROUTES
# =========================
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        "home.html",
        {"request": request}
    )


@app.get("/overlay")
async def overlay(request: Request):
    return templates.TemplateResponse(
        "overlay.html",
        {"request": request}
    )


# =========================
# WEBSOCKET
# =========================
@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await ws.accept()
    clients.add(ws)

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)


# =========================
# CONTROL
# =========================
@app.get("/start")
async def start():
    MATCH["running"] = True
    return {"status": "started"}


@app.get("/stop")
async def stop():
    MATCH["running"] = False
    return {"status": "stopped"}