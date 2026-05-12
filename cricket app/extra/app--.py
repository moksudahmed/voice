from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
import asyncio
import random
import requests
from bs4 import BeautifulSoup
from game_engine import ai_commentry
app = FastAPI()

# =========================
# CLIENTS
# =========================
clients = set()

# =========================
# MATCH STATE
# =========================
MATCH = {
    "running": False,
    "url": None,

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
# UTILS
# =========================
def play_ball():
    return random.choice(["0", "1", "1", "2", "4", "6", "W"])

def scene_logic(ball):
    if ball == "6":
        return "CROWD"
    if ball == "W":
        return "REPLAY"
    return "LIVE"

async def push(data):
    dead = set()
    for ws in clients:
        try:
            await ws.send_json(data)
        except:
            dead.add(ws)
    for d in dead:
        clients.remove(d)

# =========================
# SCRAPER (SAFE)
# =========================
def scrape_match_data(url):
    try:
        r = requests.get(url, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        import re
        score = re.search(r"\d+[/\-]\d+", text)
        overs = re.search(r"\d+\.\d", text)

        return {
            "score": score.group(0).replace("-", "/") if score else "0/0",
            "overs": overs.group(0) if overs else "0.0",
            "ball": play_ball()
        }
    except:
        return None

# =========================
# ENGINE
# =========================
async def engine():
    while True:
        if not MATCH["running"]:
            await asyncio.sleep(1)
            continue

        data = None
        if MATCH["url"]:
            data = await asyncio.to_thread(scrape_match_data, MATCH["url"])

        ball = data["ball"] if data else play_ball()

        # update score
        if ball != "W":
            runs = int(ball)
            total = int(MATCH["score"].split("/")[0]) + runs
            wickets = int(MATCH["score"].split("/")[1])
        else:
            total = int(MATCH["score"].split("/")[0])
            wickets = int(MATCH["score"].split("/")[1]) + 1

        MATCH["score"] = f"{total}/{wickets}"

        # overs
        over, ball_no = map(int, MATCH["overs"].split("."))
        ball_no += 1
        if ball_no == 6:
            ball_no = 0
            over += 1
        MATCH["overs"] = f"{over}.{ball_no}"

        # this over
        MATCH["this_over"].append(ball)
        if len(MATCH["this_over"]) > 6:
            MATCH["this_over"].pop(0)

        payload = {
            "team1": MATCH["team1"],
            "team2": MATCH["team2"],
            "score": MATCH["score"],
            "overs": MATCH["overs"],
            "this_over": MATCH["this_over"],
            "scene": scene_logic(ball)
        }

        await push(payload)
        await asyncio.sleep(1.5)

# =========================
# WEBSOCKET
# =========================
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.remove(ws)

# =========================
# ROUTES
# =========================
@app.get("/")
def home():
    return HTMLResponse("""
    <h1>🏏 Cricket Engine</h1>
    <input id="url" placeholder="Match URL">
    <button onclick="start()">START</button>

    <br><br>
    <a href="/overlay">🎥 Open Overlay</a>

    <script>
    function start(){
        fetch("/start?url=" + document.getElementById("url").value)
    }
    </script>
    """)

@app.get("/overlay")
def overlay():
    return FileResponse("templates/overlay.html")

@app.get("/start")
async def start(url: str):
    MATCH["url"] = url
    MATCH["running"] = True
    return {"status": "started"}

@app.get("/stop")
async def stop():
    MATCH["running"] = False
    return {"status": "stopped"}

# =========================
# STARTUP
# =========================
@app.on_event("startup")
async def startup():
    asyncio.create_task(engine())




from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import asyncio
import random
import requests
from bs4 import BeautifulSoup

app = FastAPI()

# =========================
# CONNECTIONS
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
    global last_scene, obs

    if not obs:
        return

    if scene not in OBS_SCENES:
        return

    if scene == last_scene:
        return

    try:
        obs.set_current_program_scene(scene)
        last_scene = scene
        print(f"🎬 OBS SWITCHED → {scene}")
    except Exception as e:
        print("OBS ERROR:", e)

# =========================
# MATCH STATE (DEFINE FIRST)
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

MATCH.update({
    "team1": "TEAM A",
    "team2": "TEAM B",
    "this_over": [],
    "striker": {"name": "Batter A", "runs": 0, "balls": 0},
    "non_striker": {"name": "Batter B", "runs": 0, "balls": 0},
    "bowler": {"name": "Bowler X", "runs": 0, "overs": 0.0},
    "partnership_runs": 0,
    "partnership_balls": 0
})
# =========================
# MATCH STATE
# =========================
MATCH2 = {
    "running": False,
    "title": "LIVE MATCH",
    "score": 0,
    "wickets": 0,
    "over": 0,
    "ball": 0,
    "url": None
}

COMMENTARY = {
    "0": "Dot ball! Solid defense.",
    "1": "Quick single taken.",
    "2": "Two runs added.",
    "4": "FOUR! Beautiful shot!",
    "6": "SIX!! Into the crowd!",
    "W": "WICKET! Massive breakthrough!"
}

# =========================
# UTIL
# =========================
def scrape_title(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.title.text.strip() if soup.title else "LIVE MATCH"
    except:
        return "LIVE MATCH"


def play_ball():
    return random.choice(["0", "1", "1", "2", "4", "6", "W"])


def update(ball):
    if ball == "W":
        MATCH["wickets"] += 1
    else:
        MATCH["score"] += int(ball)

    MATCH["ball"] += 1
    if MATCH["ball"] == 6:
        MATCH["ball"] = 0
        MATCH["over"] += 1


def scene_logic(ball):
    if ball == "6":
        return "CROWD"
    if ball == "W":
        return "REPLAY"
    return "LIVE"


# =========================
# PUSH SYSTEM (SINGLE PIPELINE)
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
# GAME ENGINE (ONLY LOOP)
# =========================
import asyncio
import re
import requests
from bs4 import BeautifulSoup

import requests
from bs4 import BeautifulSoup
import re


import requests
from bs4 import BeautifulSoup
import re

def scrape_match_data(url: str):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        text = soup.get_text(" ", strip=True)

        # SCORE
        import re
        score_match = re.search(r"(\\d{1,3})[/\\-](\\d{1,2})", text)
        score = score_match.group(0).replace("-", "/") if score_match else "0/0"

        # OVERS
        overs_match = re.search(r"(\\d{1,2}\\.\\d)", text)
        overs = overs_match.group(0) if overs_match else "0.0"

        # BALL RESULT
        ball = "0"
        boxes = soup.find_all("div", class_="result-box")
        if boxes:
            last = boxes[-1]
            span = last.find("span", class_="font1")
            if span:
                ball = span.text.strip()

        return {
            "score": score,
            "overs": overs,
            "ball": ball
        }

    except Exception as e:
        print("SCRAPE ERROR:", e)
        return None
        
def scrape_match_data2(url: str):
    import requests
    from bs4 import BeautifulSoup
    import re

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        # =========================
        # TITLE
        # =========================
        title = soup.title.text.strip() if soup.title else "LIVE MATCH"

        # =========================
        # SCORE (fallback text scan)
        # =========================
        text = soup.get_text(" ", strip=True)

        score = "0/0"
        match = re.search(r"\d{1,3}[/\-]\d{1,2}", text)
        if match:
            score = match.group(0).replace("-", "/")

        # =========================
        # OVERS
        # =========================
        overs = "0.0"
        over_match = re.search(r"\d{1,2}\.\d", text)
        if over_match:
            overs = over_match.group(0)

        # =========================
        # 🎯 BALL RESULT (THIS IS YOUR TARGET)
        # =========================
        ball_result = None

        result_boxes = soup.find_all("div", class_="result-box")

        if result_boxes:
            # take LAST result (latest ball)
            last_box = result_boxes[-1]

            span = last_box.find("span", class_="font1")
            if span:
                ball_result = span.get_text(strip=True)

        # fallback if not found
        if not ball_result:
            ball_result = "•"

        # =========================
        # COMMENTARY (based on result)
        # =========================
        commentary_map = {
            "0": "Dot ball",
            "1": "Single taken",
            "2": "Two runs",
            "3": "Three runs",
            "4": "FOUR!",
            "6": "SIX!",
            "W": "WICKET!"
        }

        commentary = commentary_map.get(ball_result, "Live play...")

        # =========================
        # RETURN FULL DATA
        # =========================
        return {
            "title": title,
            "score": score,
            "overs": overs,
            "ball": ball_result,
            "commentary": commentary
        }

    except Exception as e:
        print("SCRAPER ERROR:", e)

        return {
            "title": "LIVE MATCH",
            "score": "0/0",
            "overs": "0.0",
            "ball": "-",
            "commentary": "No data"
        }
        
async def engine():
    while True:
        if not MATCH["running"]:
            await asyncio.sleep(1)
            continue

        data = await asyncio.to_thread(scrape_match_data, MATCH["url"]) if MATCH["url"] else None

        if data:
            ball = data["ball"]
            MATCH["score"] = data["score"]
            MATCH["overs"] = data["overs"]
        else:
            ball = play_ball()
            update(ball)
            MATCH["score"] = f"{MATCH['score']}/{MATCH['wickets']}"
            MATCH["overs"] = f"{MATCH['over']}.{MATCH['ball']}"

        # =========================
        # THIS OVER TRACKER
        # =========================
        MATCH["this_over"].append(ball)
        if len(MATCH["this_over"]) > 6:
            MATCH["this_over"].pop(0)

        # =========================
        # UPDATE BATTERS
        # =========================
        striker = MATCH["striker"]

        if ball != "W":
            runs = int(ball) if ball.isdigit() else 0
            striker["runs"] += runs

        striker["balls"] += 1

        # rotate strike
        if ball in ["1", "3"]:
            MATCH["striker"], MATCH["non_striker"] = MATCH["non_striker"], MATCH["striker"]

        # =========================
        # PARTNERSHIP
        # =========================
        MATCH["partnership_runs"] += int(ball) if ball.isdigit() else 0
        MATCH["partnership_balls"] += 1

        # =========================
        # CRR CALCULATION
        # =========================
        try:
            runs = int(MATCH["score"].split("/")[0])
            ov = float(MATCH["overs"])
            crr = round(runs / ov, 2) if ov > 0 else 0
        except:
            crr = 0

        # =========================
        # BOWLER (FAKE SIMPLE)
        # =========================
        MATCH["bowler"]["runs"] += int(ball) if ball.isdigit() else 0

        # =========================
        # BUILD FINAL PAYLOAD
        # =========================
        payload = {
            "team1": MATCH["team1"],
            "team2": MATCH["team2"],

            "score": MATCH["score"],
            "overs": MATCH["overs"],

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
            "bowler_fig": f"{MATCH['bowler']['runs']}-0 ({MATCH['overs']})",

            "scene": scene_logic(ball)
        }

        # SEND TO OVERLAY
        await push(payload)

        # OBS SWITCH
        switch_scene(payload["scene"])

        await asyncio.sleep(1.2)
        
async def engine2():
    while True:

        if not MATCH["running"]:
            await asyncio.sleep(1)
            continue

        # =========================
        # SAFE SCRAPER CALL
        # =========================
        match_data = await asyncio.to_thread(
            scrape_match_data,
            MATCH["url"]
        ) if MATCH["url"] else None
        print(match_data)
        if not match_data:
            ball = play_ball()
            update(ball)

            match_data = {
                "title": MATCH["title"],
                "score": f"{MATCH['score']}/{MATCH['wickets']}",
                "overs": f"{MATCH['over']}.{MATCH['ball']}",
                "commentary": COMMENTARY[ball],
                "scene": scene_logic(ball)
            }
        else:
            match_data["scene"] = scene_logic(match_data["commentary"])

        #print("📡", match_data["title"], match_data["score"])

        await push(match_data)
        switch_scene(match_data["scene"])

        await asyncio.sleep(1.2)
async def engine2():
    while True:
        if not MATCH["running"]:
            await asyncio.sleep(1)
            continue

        ball = play_ball()
        update(ball)

        payload = {
            "title": MATCH["title"],
            "score": f"{MATCH['score']}/{MATCH['wickets']}",
            "overs": f"{MATCH['over']}.{MATCH['ball']}",
            "commentary": COMMENTARY[ball],
            "scene": scene_logic(ball)
        }
        print(payload["title"])
        # SEND TO OVERLAY
        await push(payload)

        # OBS SCENE SWITCH (FIXED)
        switch_scene(payload["scene"])

        await asyncio.sleep(1.5)


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
# START FROM URL (FIXED + SAFE)
# =========================
@app.get("/start-url")
async def start_url(url: str):
    MATCH["url"] = url
    MATCH["title"] = scrape_title(url)

    MATCH["score"] = 0
    MATCH["wickets"] = 0
    MATCH["over"] = 0
    MATCH["ball"] = 0
    MATCH["running"] = True

    # 🔥 FORCE FIRST FRAME (CRITICAL FIX)
    await push({
        "title": MATCH["title"],
        "score": "0/0",
        "overs": "0.0",
        "commentary": "🏏 MATCH STARTED",
        "scene": "LIVE"
    })

    print("🚀 MATCH STARTED FROM URL:", url)

    return {"status": "started", "title": MATCH["title"]}


@app.get("/stop")
async def stop():
    MATCH["running"] = False
    return {"status": "stopped"}


# =========================
# HOME
# =========================
@app.get("/")
def home():
    return FileResponse("templates/home.html")


# =========================
# TV OVERLAY (PRO SCOREBOARD)
# =========================

@app.get("/overlay")
def overlay():
    return FileResponse("templates/template2.html")


# =========================
# STARTUP FIX (IMPORTANT)
# =========================
@app.on_event("startup")
async def startup():
    init_obs()
    asyncio.create_task(engine())
    print("🏏 ENGINE + OBS SYSTEM READY")