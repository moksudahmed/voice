from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import asyncio
import random
import requests
from bs4 import BeautifulSoup
import re

app = FastAPI()

# =========================
# CLIENTS
# =========================
clients = set()

# =========================
# OBS SETUP
# =========================
try:
    from obsws_python import ReqClient
    OBS_ENABLED = True
except:
    ReqClient = None
    OBS_ENABLED = False

obs = None
last_scene = None

OBS_SCENES = ["LIVE", "REPLAY", "CROWD", "DRONE"]

def init_obs():
    global obs
    if not OBS_ENABLED:
        print("⚠ OBS SDK not installed")
        return

    try:
        obs = ReqClient(host="localhost", port=4455, password="jbuDLaKfxUZc6c7m")
        print("✅ OBS CONNECTED")
    except Exception as e:
        print("❌ OBS ERROR:", e)
        obs = None


def switch_scene(scene: str):
    global last_scene

    if not obs:
        return

    if scene not in OBS_SCENES:
        return

    if scene == last_scene:
        return

    try:
        obs.set_current_program_scene(scene)
        last_scene = scene
        print(f"🎬 OBS → {scene}")
    except Exception as e:
        print("OBS ERROR:", e)


# =========================
# MATCH STATE
# =========================
MATCH = {
    "running": False,
    "url": None,
    "title": "LIVE MATCH",

    "team1": "TEAM A",
    "team2": "TEAM B",

    "score": "0/0",
    "overs": "0.0",

    "this_over": [],

    "striker": {"name": "Batter A", "runs": 0, "balls": 0},
    "non_striker": {"name": "Batter B", "runs": 0, "balls": 0},

    "bowler": {"name": "Bowler X", "runs": 0},

    "partnership_runs": 0,
    "partnership_balls": 0
}

# =========================
# COMMENTARY
# =========================
COMMENTARY = {
    "0": "Dot ball!",
    "1": "Single taken",
    "2": "Two runs",
    "4": "FOUR!",
    "6": "SIX!",
    "W": "WICKET!"
}

# =========================
# SCRAPER
# =========================
def scrape_match(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")

        text = soup.get_text(" ", strip=True)

        score_match = re.search(r"(\\d{1,3})[/\\-](\\d{1,2})", text)
        score = score_match.group(0).replace("-", "/") if score_match else "0/0"

        over_match = re.search(r"(\\d{1,2}\\.\\d)", text)
        overs = over_match.group(0) if over_match else "0.0"

        ball = "0"
        boxes = soup.find_all("div", class_="result-box")
        if boxes:
            span = boxes[-1].find("span", class_="font1")
            if span:
                ball = span.text.strip()

        return score, overs, ball

    except:
        return None, None, None


# =========================
# PUSH
# =========================
async def push(data):
    dead = set()

    for ws in clients.copy():
        try:
            await ws.send_json(data)
        except:
            dead.add(ws)

    for d in dead:
        clients.discard(d)


# =========================
# ENGINE
# =========================
async def engine():
    while True:
        if not MATCH["running"]:
            await asyncio.sleep(1)
            continue

        score, overs, ball = await asyncio.to_thread(scrape_match, MATCH["url"])

        # fallback simulation
        if not score:
            ball = random.choice(["0", "1", "2", "4", "6", "W"])
            score = MATCH["score"]
            overs = MATCH["overs"]

        # update this over
        MATCH["this_over"].append(ball)
        if len(MATCH["this_over"]) > 6:
            MATCH["this_over"].pop(0)

        # striker update
        striker = MATCH["striker"]

        if ball != "W":
            runs = int(ball) if ball.isdigit() else 0
            striker["runs"] += runs
            MATCH["partnership_runs"] += runs

        striker["balls"] += 1
        MATCH["partnership_balls"] += 1

        # rotate strike
        if ball in ["1", "3"]:
            MATCH["striker"], MATCH["non_striker"] = MATCH["non_striker"], MATCH["striker"]

        # CRR
        try:
            r = int(score.split("/")[0])
            o = float(overs)
            crr = round(r / o, 2) if o > 0 else 0
        except:
            crr = 0

        # scene logic
        scene = "LIVE"
        if ball == "6":
            scene = "CROWD"
        elif ball == "W":
            scene = "REPLAY"

        # payload
        payload = {
            "team1": MATCH["team1"],
            "team2": MATCH["team2"],

            "score": score,
            "overs": overs,

            "crr": str(crr),
            "partnership": f"{MATCH['partnership_runs']} ({MATCH['partnership_balls']})",

            "this_over": MATCH["this_over"],

            "striker": MATCH["striker"]["name"],
            "striker_runs": MATCH["striker"]["runs"],
            "striker_balls": MATCH["striker"]["balls"],

            "non_striker": MATCH["non_striker"]["name"],
            "non_striker_runs": MATCH["non_striker"]["runs"],
            "non_striker_balls": MATCH["non_striker"]["balls"],

            "bowler": MATCH["bowler"]["name"],
            "bowler_fig": f"{MATCH['bowler']['runs']}-0",

            "scene": scene
        }

        await push(payload)
        switch_scene(scene)

        await asyncio.sleep(1.2)


# =========================
# WEBSOCKET
# =========================
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients.discard(websocket)


# =========================
# START FROM URL
# =========================
@app.get("/start-url")
async def start_url(url: str):
    MATCH["url"] = url
    MATCH["running"] = True

    await push({
        "team1": "TEAM A",
        "team2": "TEAM B",
        "score": "0/0",
        "overs": "0.0",
        "crr": "0.00",
        "partnership": "0 (0)",
        "this_over": [],
        "striker": "Batter A",
        "striker_runs": 0,
        "striker_balls": 0,
        "non_striker": "Batter B",
        "non_striker_runs": 0,
        "non_striker_balls": 0,
        "bowler": "Bowler X",
        "bowler_fig": "0-0",
        "scene": "LIVE"
    })

    return {"status": "started"}


@app.get("/stop")
def stop():
    MATCH["running"] = False
    return {"status": "stopped"}


# =========================
# HOME
# =========================
@app.get("/")
def home():
    return HTMLResponse("""
    <html>
    <body style="background:#0b1220;color:white;font-family:sans-serif;padding:40px;">
    <h1>🏏 PRO CRICKET ENGINE</h1>

    <input id="url" style="width:400px;padding:10px;">
    <button onclick="start()">START</button>

    <br><br>
    <a href="/overlay">OPEN OVERLAY</a>

    <script>
    function start(){
        fetch("/start-url?url=" + encodeURIComponent(document.getElementById("url").value))
    }
    </script>

    </body>
    </html>
    """)


# =========================
# OVERLAY
# =========================
@app.get("/overlay")
def overlay():
    return HTMLResponse("""
    <html>
    <body style="margin:0;background:transparent;color:white;font-family:Arial">

    <div id="score" style="font-size:40px">0/0</div>
    <div id="overs">0.0</div>
    <div id="crr"></div>
    <div id="commentary"></div>

    <script>
    const ws = new WebSocket("ws://" + location.host + "/ws");

    ws.onmessage = (e)=>{
        let d = JSON.parse(e.data);
        document.getElementById("score").innerText = d.score;
        document.getElementById("overs").innerText = d.overs;
        document.getElementById("crr").innerText = "CRR: " + d.crr;
    };
    </script>

    </body>
    </html>
    """)


# =========================
# STARTUP
# =========================
@app.on_event("startup")
async def startup():
    init_obs()
    asyncio.create_task(engine())
    print("🏏 ENGINE READY")