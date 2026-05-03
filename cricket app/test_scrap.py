from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
import threading
import time
import re
import asyncio
from playwright.sync_api import sync_playwright

app = FastAPI()

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
# GLOBAL STATE
# =========================
STATE = {
    "url": None,
    "data": {
        "team_a": "WAIT",
        "team_b": "SOURCE",
        "score": "0/0",
        "overs": "0.0",
        "status": "STARTING",
        "scene": "LIVE"
    }
}


# =========================
# SCORE PARSER
# =========================
def parse_score(text):
    match = re.search(r'(\d+)-(\d)(\d+)\.([0-5])', text)
    if not match:
        return None

    runs = int(match.group(1))
    wickets = int(match.group(2))
    over = int(match.group(3))
    ball = int(match.group(4))

    return runs, wickets, over, ball


# =========================
# SCENE LOGIC
# =========================
def scene_logic(text):
    if "WICKET" in text:
        return "REPLAY"
    if "6" in text or "SIX" in text:
        return "CROWD"
    return "LIVE"


# =========================
# SCRAPER LOOP
# =========================
def scrape_loop():
    global STATE

    while True:
        url = STATE["url"]

        if not url:
            time.sleep(2)
            continue

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                print("VISITING:", url)

                page.goto(url, timeout=60000)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(3000)

                text = page.inner_text("body")
                lines = text.splitlines()

                # =========================
                # TEAMS
                # =========================
                team_a = lines[0] if len(lines) > 0 else "TEAM A"
                team_b = lines[1] if len(lines) > 1 else "TEAM B"

                # =========================
                # SCORE
                # =========================
                score_data = parse_score(text)

                if score_data:
                    runs, wickets, over, ball = score_data
                    score = f"{runs}/{wickets}"
                    overs = f"{over}.{ball}"
                else:
                    score = "0/0"
                    overs = "0.0"

                # =========================
                # STATUS
                # =========================
                status = lines[16] if len(lines) > 16 else "LIVE"

                # =========================
                # OBS SCENE DECISION
                # =========================
                scene = scene_logic(text)

                # =========================
                # UPDATE STATE
                # =========================
                STATE["data"] = {
                    "team_a": team_a,
                    "team_b": team_b,
                    "score": score,
                    "overs": overs,
                    "status": status,
                    "scene": scene
                }

                # =========================
                # OBS SWITCH
                # =========================
                switch_scene(scene)

                print("UPDATED:", STATE["data"])

                browser.close()

        except Exception as e:
            STATE["data"] = {
                "team_a": "ERROR",
                "team_b": "SCRAPER",
                "score": "0/0",
                "overs": "0.0",
                "status": str(e),
                "scene": "LIVE"
            }

        time.sleep(2)


# =========================
# START THREAD + OBS INIT
# =========================
init_obs()
threading.Thread(target=scrape_loop, daemon=True).start()


# =========================
# SET URL
# =========================
@app.post("/set-url")
def set_url(payload: dict):
    STATE["url"] = payload.get("url")
    return {"status": "ok", "url": STATE["url"]}


# =========================
# WEBSOCKET
# =========================
# ========================= # WEBSOCKET # ========================= 
@app.websocket("/ws") 
async def ws(websocket: WebSocket): 
    await websocket.accept() 
    print("WS CONNECTED") 
    try: 
        while True: 
            await websocket.send_json(STATE["data"]) 
            await asyncio.sleep(1) 
            #❗ FIX: non-blocking 
    except WebSocketDisconnect: print("WS CLOSED")


# =========================
# OVERLAY
# =========================


@app.get("/overlay")
def overlay():
    return FileResponse("templates/overlay.html")
# =========================
# CONTROL PANEL
# =========================
@app.get("/control")
def control():
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<body style="font-family:Arial;padding:40px">

<h2>🏏 OBS Cricket Controller</h2>

<input id="url" style="width:400px;padding:10px" placeholder="Match URL">
<br><br>
<button onclick="start()">START</button>

<p id="msg"></p>

<script>
function start(){
    fetch("/set-url", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({url: document.getElementById("url").value})
    });

    document.getElementById("msg").innerText = "Running...";
}
</script>

</body>
</html>
    """)