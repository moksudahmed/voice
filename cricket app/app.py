from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from playwright.sync_api import sync_playwright
from fastapi.responses import HTMLResponse
import asyncio
import random
import requests
import time
from bs4 import BeautifulSoup
import asyncio
import re
#from run_old import load
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

def parse_score(text):
    """
    CREX format: '47-05.1'
    Means: runs=47, wickets=0, over=5, ball=1
    Pattern: {runs}-{wickets}{over}.{ball}
    """
    match = re.search(r'(\d+)-(\d)(\d+)\.([0-5])', text)
    if not match:
        return None

    runs    = int(match.group(1))
    wickets = int(match.group(2))  # single digit: 0-9
    over    = int(match.group(3))  # remaining digits after wicket
    ball    = int(match.group(4))  # decimal part, always 0-5

    return runs, wickets, over, ball


def clean_name(name):
    """
    Remove unwanted text before actual player name
    """
    # Keep only last 2–3 words (typical cricket name)
    words = name.strip().split()
    return " ".join(words[-2:])

def remove_first_part(name):
    parts = name.split(" ", 1)
    return parts[1] if len(parts) > 1 else name


def parse_bowler(text):
    """
    Extract bowler name, wickets, runs conceded, and overs from text.
    """

    try:
        

        pattern = r'([A-Z][A-Za-z\.]*(?:\s[A-Z][A-Za-z]+)+|\b[A-Z]\s?[A-Za-z]+)\s+(\d+)-(\d+)\s*\(([\d\.]+)\)'
        match = re.search(pattern, text)

        if not match:
            print("❌ No match found")
            return None

        bowler = match.group(1).strip()
        wickets = int(match.group(2))
        runs = int(match.group(3))
        overs = match.group(4)

        print("✅ MATCH FOUND")

        return {
            "bowler": bowler,
            "runs_conceded": runs,
            "wickets": wickets,
            "overs": overs
        }

    except Exception as e:
        return {"error": str(e)}
        
def parse_batsmen(text):
    """
    Extract exactly 2 batsmen (clean & accurate)
    """

    # Normalize
    text = text.replace("\r", "").strip()

    # 🔥 Remove unwanted UI text before parsing
    remove_words = [
        "Match info", "Live", "Scorecard",
        "Commentary", "Over", "Projected Score"
    ]

    for word in remove_words:
        text = text.replace(word, "")

    # 👉 Core pattern (with + separator)
    pattern = r'''
        ([A-Z][a-zA-Z\s\.]+?)\s+
        (\d+)\s+\((\d+)\)\s*
        \+\s*
        ([A-Z][a-zA-Z\s\.]+?)\s+
        (\d+)\s+\((\d+)\)
    '''

    match = re.search(pattern, text, re.VERBOSE)

    if match:
        return [
            {
                "name": remove_first_part(clean_name(match.group(1))),
                "runs": int(match.group(2)),
                "balls": int(match.group(3)),
            },
            {
                "name": remove_first_part(clean_name(match.group(4))),
                "runs": int(match.group(5)),
                "balls": int(match.group(6)),
            }
        ]

    return []

import asyncio
from playwright.async_api import async_playwright

async def load(url):
    global welcome_played

    print("🚀 SYSTEM STARTED...")
    print("URL:", url)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )

            page = await browser.new_page()

            await page.goto(url, timeout=60000)
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(3000)

            while True:
                try:
                    # 🔁 refresh page
                    await page.reload()
                    await page.wait_for_timeout(2000)

                    text = await page.inner_text("body")
                    lines = text.splitlines()

                    # =========================
                    # PARSE DATA
                    # =========================
                    score_data = parse_score(text)
                    print("PARSED:", score_data)

                    runs, wickets, over, ball = score_data

                    # =========================
                    # STATUS MESSAGE SAFE
                    # =========================
                    last_status_message = ""

                    if len(lines) > 17:
                        if "CRR" in lines[17]:
                            last_status_message = lines[16] if len(lines) > 16 else ""
                        else:
                            last_status_message = lines[17]

                    print("STATUS:", last_status_message)

                    batsmen = parse_batsmen(text)
                    bowler = parse_bowler(text)

                    print("BATSMEN:", batsmen)
                    print("BOWLER:", bowler)

                    # =========================
                    # BUILD PAYLOAD
                    # =========================
                    payload = {
                        "runs": runs,
                        "wickets": wickets,
                        "over": over,
                        "ball": ball,
                        "status": last_status_message,
                        "batsmen": batsmen,
                        "bowler": bowler,
                        "scene": "LIVE"  # you can enhance with logic
                    }

                    # =========================
                    # SEND + OBS
                    # =========================
                    await push(payload)
                    switch_scene(payload["scene"])

                except Exception as e:
                    print("⚠ LOOP ERROR:", e)

                # ⏱ NON-BLOCKING DELAY
                await asyncio.sleep(10)

    except Exception as e:
        print("❌ PLAYWRIGHT FAILED:", e)

    finally:
        try:
            await browser.close()
        except:
            pass
async def engine():
    while True:
        if not MATCH["running"]:
            await asyncio.sleep(1)
            continue
        print("Hello")
        await asyncio.to_thread(load, MATCH["url"]) if MATCH["url"] else None
        #print(data)
        #load(MATCH["url"])



        # OBS SWITCH
        #switch_scene(payload["scene"])

        await asyncio.sleep(0.2)
    

async def engine2():
    while True:
        if not MATCH["running"]:
            await asyncio.sleep(1)
            continue
        print("Hello")
        data = await asyncio.to_thread(load, MATCH["url"]) if MATCH["url"] else None
        print(data)
        #load(MATCH["url"])
        if data:
            ball = data["ball"]
            MATCH["score"] = data["score"]
            MATCH["overs"] = data["overs"]
        else:
            ball = play_ball()
            #update(ball)
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
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
<title>CRICKET ENGINE PRO</title>
<style>
body{margin:0;background:#0b1220;color:white;font-family:Segoe UI;}
.container{padding:40px;max-width:900px;margin:auto;}
.card{background:#111c33;padding:20px;border-radius:12px;}
input,button{padding:10px;margin:5px;}
button{background:#00ffcc;border:none;font-weight:bold;cursor:pointer;}
</style>
</head>
<body>

<div class="container">
<h1>🏏 CRICKET ENGINE PRO</h1>

<div class="card">
<h3>Start Match From URL</h3>
<input id="url" style="width:80%" placeholder="Paste match URL">
<button onclick="start()">START</button>
</div>

<div class="card">
<a href="/overlay">🎥 OPEN OVERLAY</a>
</div>

</div>

<script>
function start(){
fetch("/start-url?url=" + encodeURIComponent(document.getElementById("url").value));
}
</script>

</body>
</html>
""")


# =========================
# TV OVERLAY (PRO SCOREBOARD)
# =========================
@app.get("/overlay")
def overlay():
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
<style>
body{
margin:0;
background:transparent;
font-family:'Segoe UI',Arial;
color:white;
overflow:hidden;
}

/* =========================
   TOP SCOREBOARD
========================= */
.top-bar{
position:absolute;
top:10px;
left:50%;
transform:translateX(-50%);
width:90%;
display:flex;
justify-content:space-between;
background:linear-gradient(90deg,#8b0000,#ff0000);
border-radius:12px;
padding:10px 20px;
box-shadow:0 0 20px rgba(0,0,0,0.6);
}

.team{
font-size:18px;
font-weight:bold;
}

.score{
font-size:40px;
font-weight:800;
}

.overs{
font-size:16px;
opacity:0.9;
}

/* =========================
   MID INFO BAR
========================= */
.mid-bar{
position:absolute;
top:90px;
left:50%;
transform:translateX(-50%);
width:90%;
display:flex;
justify-content:space-between;
background:#1e3a8a;
padding:8px 15px;
border-radius:8px;
font-size:14px;
}

.label{
color:#facc15;
font-weight:bold;
}

/* =========================
   THIS OVER
========================= */
.over-bar{
position:absolute;
top:140px;
left:50%;
transform:translateX(-50%);
display:flex;
gap:6px;
}

.ball{
width:28px;
height:28px;
display:flex;
align-items:center;
justify-content:center;
border-radius:6px;
font-weight:bold;
background:#111;
}

.b4{background:#2563eb;}
.b6{background:#16a34a;}
.bW{background:#dc2626;}
.b0{background:#444;}

/* =========================
   PLAYER CARDS
========================= */
.players{
position:absolute;
bottom:20px;
left:50%;
transform:translateX(-50%);
display:flex;
gap:20px;
}

.card{
background:rgba(0,0,0,0.85);
padding:12px 18px;
border-radius:10px;
min-width:220px;
text-align:center;
box-shadow:0 0 15px rgba(0,0,0,0.7);
}

.name{
font-weight:bold;
font-size:16px;
}

.stats{
font-size:22px;
font-weight:bold;
color:#00ffcc;
}

/* =========================
   BOWLER CARD
========================= */
.bowler{
position:absolute;
bottom:20px;
right:30px;
background:rgba(0,0,0,0.85);
padding:12px 18px;
border-radius:10px;
min-width:180px;
text-align:center;
}

/* =========================
   ANIMATION
========================= */
.top-bar,.mid-bar,.players{
animation:fade 0.5s ease;
}

@keyframes fade{
from{opacity:0;transform:translateY(-10px);}
to{opacity:1;transform:translateY(0);}
}
</style>
</head>

<body>

<!-- TOP BAR -->
<div class="top-bar">
    <div>
        <div class="team" id="team1">TEAM A</div>
        <div class="score" id="score">0/0</div>
        <div class="overs" id="overs">0.0</div>
    </div>

    <div>
        <div class="team" id="team2">TEAM B</div>
        <div style="font-size:30px;font-weight:bold;">BOWL</div>
    </div>
</div>

<!-- MID BAR -->
<div class="mid-bar">
    <div><span class="label">CRR:</span> <span id="crr">0.00</span></div>
    <div><span class="label">P'SHIP:</span> <span id="pship">0 (0)</span></div>
</div>

<!-- THIS OVER -->
<div class="over-bar" id="overBar"></div>

<!-- BATTERS -->
<div class="players">
    <div class="card">
        <div class="name" id="s_name">Striker</div>
        <div class="stats" id="s_stats">0 (0)</div>
    </div>

    <div class="card">
        <div class="name" id="ns_name">Non-Striker</div>
        <div class="stats" id="ns_stats">0 (0)</div>
    </div>
</div>

<!-- BOWLER -->
<div class="bowler">
    <div class="name" id="bowler">Bowler</div>
    <div class="stats" id="b_stats">0-0 (0)</div>
</div>

<script>
const ws = new WebSocket("ws://" + location.host + "/ws");

ws.onmessage = (e)=>{
    let d = JSON.parse(e.data);

    document.getElementById("team1").innerText = d.team1 || "TEAM A";
    document.getElementById("team2").innerText = d.team2 || "TEAM B";

    document.getElementById("score").innerText = d.score || "0/0";
    document.getElementById("overs").innerText = d.overs || "0.0";

    document.getElementById("crr").innerText = d.crr || "0.00";
    document.getElementById("pship").innerText = d.partnership || "0 (0)";

    document.getElementById("s_name").innerText = d.striker || "-";
    document.getElementById("s_stats").innerText =
        (d.striker_runs || 0) + " (" + (d.striker_balls || 0) + ")";

    document.getElementById("ns_name").innerText = d.non_striker || "-";
    document.getElementById("ns_stats").innerText =
        (d.non_striker_runs || 0) + " (" + (d.non_striker_balls || 0) + ")";

    document.getElementById("bowler").innerText = d.bowler || "-";
    document.getElementById("b_stats").innerText = d.bowler_fig || "-";

    // THIS OVER
    let overDiv = document.getElementById("overBar");
    overDiv.innerHTML = "";

    if(d.this_over){
        d.this_over.forEach(ball=>{
            let el = document.createElement("div");
            el.className = "ball";

            if(ball == "4") el.classList.add("b4");
            else if(ball == "6") el.classList.add("b6");
            else if(ball == "W") el.classList.add("bW");
            else el.classList.add("b0");

            el.innerText = ball;
            overDiv.appendChild(el);
        });
    }
};
</script>

</body>
</html>
""")

# =========================
# STARTUP FIX (IMPORTANT)
# =========================
@app.on_event("startup")
async def startup():
    init_obs()
    asyncio.create_task(engine())
    print("🏏 ENGINE + OBS SYSTEM READY")