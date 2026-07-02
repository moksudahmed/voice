from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi import Body
import asyncio
import random
from pathlib import Path
import json
from datetime import datetime
import os
import time
import sys
import re
import hashlib
from player_list import get_playing_xi, generate_team_html
from commentry import generate_continuous_commentary, bangla_commentary, generate_full_commentary, generate_welcome_message, generate_winning_message
from bangla_commentry import generate_current_match_status
from game_status import detect_game_status, handle_break_period
from commentry_dic import WELCOME_COMMENTARY_TEMPLATES, WINNING_COMMENTARY_TEMPLATES
from commentry_dic import COMMENTARY, EXTRA_COMMENTARY
from fastapi.templating import Jinja2Templates
from utill import number_to_bangla_words
import re
from obs_config import switch_scene, init_obs, update_obs_scene
from pydantic import BaseModel
from voice import speak_bangla, speak
from scraper import scrap_page
from live_matches import get_live_matches
from live_status import detect_match_event, get_event_string, EVENT_OUTPUT_MAP
from run_events import detect_event, detect_event_advanced ,EVENT_MAP
from events import detect_cricket_event
from scorecard import load_scorecard
from scoreboard import load_data
# =========================================================
# APP
# =========================================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# STATE
# =========================================================

STATE = {
    "url": None,
    "current_playing_xi": None,
    "connected": False,
    "flags": {
        "team_a_flag": "",
        "team_a_name":"",
        "team_a_full_name": "TEAM A",        
        "team_b_flag": "",
        "team_b_name":"",
        "team_b_full_name": "TEAM B",
        "match_info": "",
        "team_a_bangla_name":"",
        "team_b_bangla_name":"",

    },
    "data": {},    
    "match_live": False,
}
SCORE_DATA = {}


clients = set()
# =========================
# GLOBALS
# =========================
FLAGS_LOADED = False
FLAGS_URL = None
STOP_ENGINE = False
START_ENGINE =False
PLAYWRIGHT = None
BROWSER = None
# =========================
# OBS SETUP
# =========================

# =========================
# SCENE LOGIC
# =========================
def scene_logic(text):
    t = text.upper()

    if "WICKET" in t:
        return "REPLAY"
    if "SIX" in t or " 6 " in t:
        return "CROWD"

    return "LIVE"




# =========================================================
# CLEANER
# =========================================================

def clean(t):
    return re.sub(r"\s+", " ", t).strip() if t else ""

def parse_match_result(text: str):
    pattern = r"(.+?)\s+won\s+by\s+(\d+)\s+(runs|wickets)"
    match = re.search(pattern, text, re.IGNORECASE)

    if not match:
        return None

    return {
        "winner": match.group(1).strip(),
        "margin": int(match.group(2)),
        "type": match.group(3).lower()
    }



# =========================================================
# FAST PARSER (OPTIMIZED FOR CREX + ANGULAR)
# =========================================================

def parse_score(text):
    match = re.search(r'(\d+)-(\d)(\d+)\.([0-5])', text)
    if not match:
        return None

    runs = int(match.group(1))
    wickets = int(match.group(2))
    over = int(match.group(3))
    ball = int(match.group(4))

    return runs, wickets, over, ball

def get_over_before_crr(text):
    lines = text.splitlines()
    try:
        for i, item in enumerate(lines):
            if "CRR" in item:
                # return previous non-empty value
                j = i - 1
                while j >= 0:
                    val = lines[j].strip()
                    if val:   # skip empty strings
                        return val
                    j -= 1
    except Exception as e:
        print("Error:", e)

    return None
async def extract_result_and_ball(page):

    try:

        # =========================
        # RESULT BOX (IMPORTANT FIX)
        # =========================
        result = await page.locator(
            ".result-box span"
        ).all_text_contents()

        result = [r.strip() for r in result if r.strip()]

        # =========================
        # BALL VALUE (4 / 6 / WICKET)
        # =========================
        ball_event = await page.locator(
            ".result-box"
        ).first.get_attribute("class")

        ball_value = None

        # fallback: read actual number inside span
        try:
            ball_value = await page.locator(
                ".result-box span"
            ).first.text_content()
            ball_value = ball_value.strip()
        except:
            pass

        return {
            "result_text": result[0] if result else "",
            "ball": ball_value,
            "type": ball_event
        }

    except Exception as e:
        print("RESULT PARSE ERROR:", e)
        return {
            "result_text": "",
            "ball": "",
            "type": ""
        }

# =========================
# UPDATE FLAGS
# =========================
async def extract_team_flags(url):

    result = {
        "team_a_name": "TEAM A",
        "team_b_name": "TEAM B",

        "team_a_full_name": "TEAM A",
        "team_b_full_name": "TEAM B",

        "team_a_flag": "",
        "team_b_flag": "",

        "match_info": ""
    }

    # ==========================================
    # VALIDATE URL
    # ==========================================
    if not url:
        return result

    browser = None

    try:

        # ==========================================
        # MATCH DETAILS URL
        # ==========================================
        url = url.rstrip("/") + "/match-details"

        async with async_playwright() as p:

            # ==========================================
            # BROWSER
            # ==========================================
            browser = await p.chromium.launch(
                headless=True
            )

            page = await browser.new_page()

            print("🌐 OPENING:", url)

            # ==========================================
            # OPEN PAGE
            # ==========================================
            await page.goto(
                url,
                timeout=60000,
                wait_until="domcontentloaded"
            )

            # ==========================================
            # WAIT FOR MAIN CONTENT
            # ==========================================
            await page.wait_for_selector(
                "#recent-matches",
                timeout=30000
            )

            # ==========================================
            # MATCH INFO
            # ==========================================
            try:

                match_info_locator = page.locator(
                    ".series-name.mob-none h1.name-wrapper span"
                ).first

                raw_match_info = (
                    await match_info_locator.inner_text()
                ).strip()

                # ======================================
                # REMOVE "Info" PART
                # ======================================
                clean_match_info = re.split(
                    r"\s+Info\s*,|\s+Info\b",
                    raw_match_info,
                    maxsplit=1
                )[0].strip()

                result["match_info"] = clean_match_info

            except Exception as e:

                print("❌ MATCH INFO ERROR:", e)

            # ==========================================
            # RECENT MATCHES SECTION
            # ==========================================
            recent_section = page.locator(
                "#recent-matches"
            )

            # ==========================================
            # TEAM BLOCKS
            # ==========================================
            team_blocks = recent_section.locator(
                ".format-match"
            )

            total_teams = await team_blocks.count()

            if total_teams < 2:

                print("❌ LESS THAN 2 TEAMS FOUND")

                return result

            # ==========================================
            # TEAM A BLOCK
            # ==========================================
            team1_block = team_blocks.nth(0)

            # FULL NAME
            team1_full_name = (
                await team1_block.locator(
                    ".form-team-name"
                ).first.inner_text()
            ).strip()

            # SHORT NAME FROM IMAGE ALT
            team1_short_name = (
                await team1_block.locator(
                    ".form-match-team img"
                ).first.get_attribute("alt")
            )

            # FLAG
            team1_flag = (
                await team1_block.locator(
                    ".form-match-team img"
                ).first.get_attribute("src")
            )

            # ==========================================
            # TEAM B BLOCK
            # ==========================================
            team2_block = team_blocks.nth(1)

            # FULL NAME
            team2_full_name = (
                await team2_block.locator(
                    ".form-team-name"
                ).first.inner_text()
            ).strip()

            # SHORT NAME FROM IMAGE ALT
            team2_short_name = (
                await team2_block.locator(
                    ".form-match-team img"
                ).first.get_attribute("alt")
            )

            # FLAG
            team2_flag = (
                await team2_block.locator(
                    ".form-match-team img"
                ).first.get_attribute("src")
            )

            # ==========================================
            # SAVE DATA
            # ==========================================
            result.update({

                # SHORT NAMES
                "team_a_name": (
                    team1_short_name or team1_full_name
                ).strip(),

                "team_b_name": (
                    team2_short_name or team2_full_name
                ).strip(),

                # FULL NAMES
                "team_a_full_name": team1_full_name,
                "team_b_full_name": team2_full_name,

                # FLAGS
                "team_a_flag": team1_flag or "",
                "team_b_flag": team2_flag or ""
            })

            print("✅ TEAM A:", result["team_a_name"])
            print("✅ TEAM B:", result["team_b_name"])

            return result

    except Exception as e:

        print("❌ FLAG ERROR:", e)

        return result

    finally:

        try:
            if browser:
                await browser.close()
        except:
            pass


async def update_team_flags(url):

    """
    Fetch and store team flags asynchronously.
    """

    try:

        data = await extract_team_flags(url)
        
        STATE["flags"] = {
            "team_a_flag": data.get("team_a_flag", ""),
            "team_b_flag": data.get("team_b_flag", ""),
            "team_a_name": data.get("team_a_name", ""),
            "team_b_name": data.get("team_b_name", ""),
            "team_a_full_name": data.get("team_a_full_name", ""),
            "team_b_full_name": data.get("team_b_full_name", ""),
            "match_info": data.get("match_info", ""),
        }

        # OPTIONAL TEAM NAME SYNC
        STATE["data"]["team_a"] = data.get(
            "team_a_name",
            "TEAM A"
        )

        STATE["data"]["team_b"] = data.get(
            "team_b_name",
            "TEAM B"
        )
        #print("Check")
        #print(STATE["data"])
        print("🏏 FLAGS UPDATED:", STATE["flags"])

        return True

    except Exception as e:

        print("❌ FLAG FETCH ERROR:", e)

        return False

# =========================
# LOAD FLAGS ONCE
# =========================
async def ensure_flags_loaded():

    global FLAGS_LOADED, FLAGS_URL

    url = STATE["url"]
    
    if not url:
        return

    # =========================
    # PREVENT RELOADING
    # =========================
    if FLAGS_LOADED and FLAGS_URL == url:
        return

    print("🏏 LOADING TEAM FLAGS...")

    success = await update_team_flags(url)

    if success:
        FLAGS_LOADED = True
        FLAGS_URL = url


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

def get_last_name(name):
    return name.strip().split()[-1]

def is_valid_flags(flags):
    return (
        flags
        and flags.get("team_a_name")
        and flags.get("team_b_name")
    )

def swap_teams(flags: dict):
    flags["team_a_name"], flags["team_b_name"] = flags.get("team_b_name"), flags.get("team_a_name")
    flags["team_a_full_name"], flags["team_b_full_name"] = flags.get("team_b_full_name"), flags.get("team_a_full_name")
    flags["team_a_flag"], flags["team_b_flag"] = flags.get("team_b_flag"), flags.get("team_a_flag")


def parse_bowler(data):
    """
    Extract exactly 2 batsmen (clean & accurate)
    """
  
    bowler = data["name"]
    bowler_fig = data["figures"]
    
       
    match = re.search(r'(\d+)-(\d+)\s*\((\d+\.\d)\)', bowler_fig)
    wickets = 0
    runs = 0
    overs = 0
    if match:
        wickets = int(match.group(1))
        runs = int(match.group(2))
        overs = match.group(3)

        #print("Wickets:", wickets)
        #print("Runs:", runs)
        #print("Overs:", overs)
        #print("Test Name", bowler)
    
    return {
            "name": remove_first_part(bowler),
            "runs_conceded": runs,
            "wickets": wickets,
            "overs": overs
        }

def parse_batsmen(data):
    """
    Extract exactly 2 batsmen (clean & accurate)
    """
    striker = data["striker"]
    striker_balls = data["striker_balls"]
    striker_runs = data["striker_runs"]
    non_striker = data["non_striker"]
    non_striker_balls = data["non_striker_balls"]
    non_striker_runs = data["non_striker_runs"]
    return [
            {
                "name": get_last_name(striker),
                "runs": int(striker_runs),
                "balls": int(striker_balls),
            },
             {
                "name": get_last_name(non_striker),
                "runs": int(non_striker_runs),
                "balls": int(non_striker_balls),
            },
        ]

def determine_start_game(event):
    if event in ["TOSS_WON_BAT_FIRST", "TOSS_COMPLETED", "TOSS_WON_BOWL_FIRST"]:
        
        commentary_text = random.choice(EXTRA_COMMENTARY[event])
        print(commentary_text)
        speak_bangla(commentary_text)  



# =========================
# SAFE SPEAK
# =========================

async def safe_speak(text):
    try:
        await asyncio.to_thread(speak, text)
    except Exception as e:
        print("Speech error:", e)


# =========================
# BROADCAST
# =========================

async def broadcast(data):
    dead = []

    for ws in list(clients):
        try:
            await ws.send_json(data)
        except:
            dead.append(ws)

    for d in dead:
        clients.remove(d)

# =========================
# OBS CONTROL (FIXED)
# =========================

async def update_obs_scene2(event_key):

    try:
        print("OBS EVENT:", event_key)

        if event_key == "OVER_COMPLETE":
            print("📺 OVER COMPLETE")
            await asyncio.sleep(30)
            switch_scene("SCOREBOARD")
            await asyncio.sleep(30)
            switch_scene("LIVE")
            return

        if event_key in {
            "INNINGS_BREAK",
            "LUNCH_BREAK",
            "TEA_BREAK",
            "RAIN_BREAK"
        }:
            switch_scene("DRONE")
            await asyncio.sleep(20)
            switch_scene("LIVE")
            return

    except Exception as e:
        print("❌ OBS ERROR:", e)
# =========================
# SCRAPER LOOP (MAIN WORKER)
# =========================

async def scraper():

    page = await BROWSER.new_page()

    last_hash = None
    last_event_signature = None

    print("🚀 SCRAPER STARTED")

    obs_ready = init_obs()
    if obs_ready:
        switch_scene("LIVE")

    while True:
        try:
            print("HEllo WORld")
            # =========================
            # WAIT UNTIL MATCH LIVE
            # =========================
            if not STATE.get("match_live"):
                await asyncio.sleep(1)
                continue

            url = STATE.get("url")
            if not url:
                await asyncio.sleep(1)
                continue

            # =========================
            # CONNECT IF NEEDED
            # =========================
            if not STATE.get("connected"):
                await page.goto(url, wait_until="domcontentloaded")

                await page.evaluate("""
                    window.__dirty = true;
                    const obs = new MutationObserver(() => {
                        window.__dirty = true;
                    });
                    obs.observe(document.body, {
                        childList: true,
                        subtree: true
                    });
                """)

                STATE["connected"] = True

            # =========================
            # SKIP IF NO CHANGE
            # =========================
            is_dirty = await page.evaluate("window.__dirty")

            if not is_dirty:
                await asyncio.sleep(0.2)
                continue

            await page.evaluate("window.__dirty = false")

            # =========================
            # SCRAPE PAGE
            # =========================
            parsed = await scrap_page(page)

            if not parsed:
                continue

            STATE["data"] = parsed

            data_hash = hashlib.md5(
                json.dumps(parsed, sort_keys=True).encode()
            ).hexdigest()

            if data_hash == last_hash:
                continue

            last_hash = data_hash

            # =========================
            # EVENT DETECTION
            # =========================
            result = parsed.get("result_boxes", [""])[0]

            event_key = detect_cricket_event(result)

            if event_key:

                event_signature = event_key

                if event_signature != last_event_signature:

                    score = parsed.get("score", "")
                    overs = parsed.get("overs", "")

                    batsman = parse_batsmen(parsed)
                    bowler = parse_bowler(
                        parsed.get("live_players", {}).get("bowler")
                    )

                    full_over = int(str(overs).split(".")[0]) if "." in str(overs) else 0

                    commentary = generate_continuous_commentary(
                        event_key,
                        batsman,
                        bowler,
                        score,
                        full_over,
                        STATE["flags"].get("team_a_name", "TEAM A"),
                        STATE["flags"].get("team_b_name", "TEAM B"),
                        event_key
                    )

                    if commentary:
                        STATE["data"]["commentary"] = commentary
                        await safe_speak(commentary)
                        print("🗣", commentary)

                    # OBS CONTROL
                    if event_key in {
                        "INNINGS_BREAK",
                        "LUNCH_BREAK",
                        "TEA_BREAK",
                        "RAIN_BREAK",
                        "OVER_COMPLETE",
                        "COMPLETED"
                    }:
                        await update_obs_scene(event_key)

                    last_event_signature = event_signature

            # =========================
            # BROADCAST
            # =========================
            await broadcast({
                **STATE["data"],
                "flags": STATE["flags"]
            })

            await asyncio.sleep(0.12)

        except Exception as e:
            print("❌ SCRAPER ERROR:", e)
            STATE["connected"] = False

            try:
                await page.close()
                page = await BROWSER.new_page()
            except:
                pass

            await asyncio.sleep(2)

# =========================================
# 🧠 AI ENGINE WRAPPER (THREAD SAFE FIX)
# =========================================
        
async def voice_announce_once(action="", status="", message=""):
    """
    Single announcement version - generates message and speaks once
    """
    try:
        # Generate the appropriate voice message
        voice_message = generate_current_match_status(action, status, message)
        
        # Speak the message if it's not empty
        if voice_message and voice_message.strip():
            # Run speak_bangla in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, speak_bangla, voice_message)
    
    except Exception as e:
        print("VOICE ERROR:", e)

        
def api_response(
    status="Unknown",
    message="",
    action=None,
    success=True,
    data=None
):
    # Create async task for voice worker without blocking
    #if action and action in ["WAIT", "LIVE", "COMPLETE", "STOP", "PAUSE", "ERROR", "UNKNOWN", "REFRESH"]:

    #    asyncio.create_task(voice_announce_once(action, status, message))
    
    return {
        "success": success,
        "status": status,
        "message": message,
        "action": action,
        "data": data or {}
    }

# =========================
# AI ENGINE (NO SCRAPER CALL!)
# =========================

async def run_ai_engine():
    url = STATE.get("url")

    if not url:
        return

    try:
        page = await BROWSER.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_load_state("networkidle")

        text = await page.inner_text("body")
        lines = text.splitlines()

        status = detect_game_status(lines)

        print("📊 STATUS:", status)
        
        # ONLY UPDATE STATE (NO LOOP CALLS)
        if "LIVE" in status or "BREAK" in status:
            STATE["match_live"] = True
                   
            switch_scene("LIVE")

        else:            
            STATE["match_live"] = False            
            switch_scene("MATCH_STATUS")
            await asyncio.sleep(10)

        await page.close()

    except Exception as e:
        print("❌ run_ai_engine error:", e)



async def get_match_status():
    url = STATE.get("url")
    if not url:
        return {
            "success": False,
            "status": "Invalid URL",
            "action": "ERROR"
        }
    try:
        page = await BROWSER.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3000)
        text = await page.inner_text("body")
        lines = text.splitlines()
        status = detect_game_status(lines)
        await page.close()
        return {
            "success": True,
            "status": status,
            "action": "UNKNOWN"  # frontend will decide
        }
    except Exception as e:
        return {
            "success": False,
            "status": "Error",
            "action": "ERROR"
        }


async def engine_loop():
    global STOP_ENGINE
    
    while not STOP_ENGINE:
        try:
            await run_ai_engine()
        except Exception as e:
            print("❌ Engine error:", e)

        await asyncio.sleep(5)

    print("🛑 Engine stopped safely")



def stop_engine(reason: str):
    global STOP_ENGINE
    print(f"🛑 ENGINE STOPPED: {reason}")
    STOP_ENGINE = True
# ==========================================================
# MAIN
# ==========================================================


app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)
app.mount(
    "/templates",
    StaticFiles(directory="templates"),
    name="templates"
)
# =========================
# INIT
# =========================


# =========================
# STARTUP
# =========================

@app.on_event("startup")
async def startup():
    global PLAYWRIGHT, BROWSER

    PLAYWRIGHT = await async_playwright().start()
    BROWSER = await PLAYWRIGHT.chromium.launch(headless=True)
    print("Engine : ",START_ENGINE)
    if START_ENGINE:        
        print("Testst")
    asyncio.create_task(engine_loop())    
    asyncio.create_task(scraper())
    asyncio.create_task(scoreboard_updater())    
   
# =========================================================
# ROUTES
# =========================================================

@app.get("/")
def home():
    return FileResponse("templates/home.html")

@app.get("/overlay")
def overlay():
    return FileResponse("templates/overlay.html")


@app.get("/welcome")
def overlay():
    return FileResponse("templates/welcome.html")

@app.post("/set-url")
async def set_url(payload: dict):
    START_ENGINE = True
    STATE["url"] = payload.get("url", "")
    STATE["connected"] = False
    # =========================
    # LOAD FLAGS ONLY ONCE
    # =========================
    obs_ready = init_obs()
    if obs_ready:        
        switch_scene("WELCOME")
        await asyncio.sleep(10)        
    await ensure_flags_loaded()
    if STATE["url"]:                
        data = await get_playing_xi(STATE["url"])
        STATE["current_playing_xi"] = data
        
    return {"ok": True}



templates = Jinja2Templates(directory="templates")
#templates = Jinja2Templates(directory="./templates")


@app.get("/api/match-status")
async def get_match_status_api():
    data = await get_match_status()
    print(data)
    return JSONResponse(content=data)

@app.get("/live-match-status", response_class=HTMLResponse)
async def dashboard(request: Request):
    #commentary = "বৃষ্টি শুরু! খেলা বন্ধ! সবাই অপেক্ষায়! লাইভে যারা আছেন—আপনারা কি মনে করেন ম্যাচ আবার শুরু হবে?"
    #speak_bangla(commentary)
    return templates.TemplateResponse(
        "match_status.html",
        {
            "request": request
        }
    )

# =========================
# LIVE MATCH API (NEW FIXED)
# =========================
@app.get("/api/matches")
async def live_matches():
    data = await get_live_matches()
    return {
        "count": len(data),
        "matches": data
    }
# =========================================================
# WEBSOCKET
# =========================================================

@app.websocket("/ws")
async def ws(websocket: WebSocket):

    await websocket.accept()
    clients.add(websocket)

    print("🔌 CLIENT CONNECTED")
    
    try:
        # =========================
        # LOAD FLAGS ONLY ONCE
        # =========================
        """await ensure_flags_loaded()
        if STATE["url"]:        
            data = await get_playing_xi(STATE["url"])
            #print(data)"""


        while True:
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        clients.remove(websocket)
        print("❌ CLIENT DISCONNECTED")


# =========================================================
# HTML PAGE
# =========================================================
@app.get("/players", response_class=HTMLResponse)
async def get_players_page(request: Request):
    """Serve the Playing XI HTML page with cached team data."""

    html_file_path = Path("templates/players.html")

    if not html_file_path.exists():
        return HTMLResponse(
            content="<h1>players.html file not found!</h1>",
            status_code=404
        )

    with open(html_file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    default_team_a = (
        '<div class="team-container">'
        '<div class="team-header team-a">No Data</div>'
        '<div class="players-grid">Waiting for data...</div>'
        '</div>'
    )

    default_team_b = (
        '<div class="team-container">'
        '<div class="team-header team-b">No Data</div>'
        '<div class="players-grid">Waiting for data...</div>'
        '</div>'
    )

    team_a_html = default_team_a
    team_b_html = default_team_b
    data_available = "false"

    try:
        data = STATE.get("current_playing_xi", {})

        if data:
            team_a_html = generate_team_html(
                data.get("team_a", {}),
                "team-a"
            )

            team_b_html = generate_team_html(
                data.get("team_b", {}),
                "team-b"
            )

            data_available = "true"

    except Exception as e:
        print(f"Error rendering Playing XI: {e}")

        team_a_html = (
            '<div class="team-container">'
            '<div class="team-header team-a">Error Loading</div>'
            '<div class="players-grid">Failed to load team data</div>'
            '</div>'
        )

        team_b_html = (
            '<div class="team-container">'
            '<div class="team-header team-b">Error Loading</div>'
            '<div class="players-grid">Failed to load team data</div>'
            '</div>'
        )

    html_content = (
        html_content
        .replace("{{ TEAM_A_HTML }}", team_a_html)
        .replace("{{ TEAM_B_HTML }}", team_b_html)
        .replace("{{ DATA_AVAILABLE }}", data_available)
    )

    return HTMLResponse(content=html_content)

@app.get("/api/playing-xi")
async def get_playing_xi_api():
    """
    Returns Playing XI data.

    Logic:
    1. Return cached data if available.
    2. Otherwise fetch from source.
    3. Save to cache.
    4. Return response.
    """

    # Ensure cache key exists
    STATE.setdefault("current_playing_xi", {})

    cached_data = STATE["current_playing_xi"]

    # Return cached data immediately
    if cached_data:
        
        return {
            "success": True,
            "team_a": cached_data.get("team_a", {}),
            "team_b": cached_data.get("team_b", {}),
            "cached": True,
        }

    url = STATE.get("url")
    if not url:
        return {
            "success": False,
            "error": "No match URL available",
            "team_a": {},
            "team_b": {},
        }

    try:
        data = await get_playing_xi(url)

        # Store only if valid data returned
        if data:
            STATE["current_playing_xi"] = data

        return {
            "success": True,
            "team_a": data.get("team_a", {}),
            "team_b": data.get("team_b", {}),
            "cached": False,
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "team_a": {},
                "team_b": {},
            },
        )

# =========================================================
# JSON API
# =========================================================

@app.get("/api/players")
async def api_players():

    data = await get_playing_xi()

    return JSONResponse(content=data)


# BACKEND CODE UPDATE (Add to your existing FastAPI app)
# =====================================================
# Add this enhanced endpoint with proper loop-compatible TTS execution

# ======================= FASTAPI ENDPOINTS =======================

@app.post("/play-welcome-commentary")
async def play_welcome_commentary(payload: dict = Body(...)):
    """
    Play welcome commentary - automatically stops previous before starting new
    """
    try:
        text = payload.get("text", "").strip()
        if not text:
            return JSONResponse({
                "success": False,
                "message": "Empty speech text"
            })
        
        # Stop any currently playing TTS first
        stop_current_tts()
        
        # Small delay to ensure cleanup
        await asyncio.sleep(0.1)
        
        # Start new TTS
        speak_bangla(text)
        
        print(f"[WELCOME COMMENTARY] Started: {text[:100]}...")
        return JSONResponse({
            "success": True,
            "message": "Commentary started"
        })
        
    except Exception as e:
        print(f"[WELCOME COMMENTARY ERROR] {e}")
        return JSONResponse({
            "success": False,
            "message": str(e)
        })

@app.post("/stop-commentary")
async def stop_commentary():
    """
    Stop currently playing commentary immediately
    """
    stop_current_tts()
    return JSONResponse({
        "success": True,
        "message": "Commentary stopped"
    })



# ======================= YOUR EXISTING CODE BELOW (KEEP EVERYTHING) =======================
# Keep all your existing WebSocket, /set-url, /api/matches, etc. here    
# Add to your existing FastAPI backend

# Store Bangla team names
bangla_team_names = {}

@app.post("/api/update-bangla-team-name")
async def update_bangla_team_name(payload: dict):
    try:
        team = payload.get("team")
        bangla_name = payload.get("bangla_name")
        if team =="Team A":
            STATE["flags"]["team_a_bangla_name"]= bangla_name
        else:
            STATE["flags"]["team_b_bangla_name"]= bangla_name
        
        print(f"[BANGLA NAME] {team} -> {bangla_name}")
        
        return {"success": True, "message": "Bangla name saved"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e)}
        )

@app.get("/api/get-bangla-team-names")
async def get_bangla_team_names():
    try:
        return {
            "success": True,
            "names": bangla_team_names
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e)}
        )
    

@app.post("/api/swap-teams")
async def swap_team(payload: dict = Body(...)):
    """Receive team swap information from dashboard"""
    batting_team = payload.get("batting_team")
    fielding_team = payload.get("fielding_team")
    
    # Store in global state
    STATE["batting_team"] = batting_team
    STATE["fielding_team"] = fielding_team
    
    swap_teams(STATE["flags"])
    print(f"🔄 Teams swapped: {batting_team} batting, {fielding_team} fielding")
    
    return JSONResponse({
        "success": True,
        "message": "Teams swapped successfully",
        "batting_team": batting_team,
        "fielding_team": fielding_team
    })

@app.post("/api/broadcast-swap")
async def broadcast_swap(payload: dict = Body(...)):
    """Broadcast team swap to all connected WebSocket clients"""
    try:
        # Broadcast to all connected WebSocket clients
        for client in clients:
            try:
                await client.send_json(payload)
            except:
                pass
        return JSONResponse({"success": True, "message": "Swap broadcasted"})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})
    

@app.get("/api/team-state")
async def get_team_state():
    """Get current team state (batting/fielding)"""
    return JSONResponse({
        "batting_team": STATE.get("batting_team", "Team A"),
        "fielding_team": STATE.get("fielding_team", "Team B"),
        "team_a_status": STATE.get("team_a_status", "Batting"),
        "team_b_status": STATE.get("team_b_status", "Fielding")
    })
# FastAPI Scoreboard API


# ==========================================
# BACKGROUND CACHE UPDATER
# ==========================================

async def scoreboard_updater():       
    while True:
        try:
            if STATE.get("url"):
                data = await load_data(STATE["url"])

                if isinstance(data, dict):
                    STATE["current_scoreboard"] = data

        except Exception as e:
            print("Scoreboard update error:", e)

        await asyncio.sleep(3)


# ==========================================
# SCOREBOARD PAGE
# ==========================================

@app.get("/scoreboard", response_class=HTMLResponse)
async def scoreboard_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="scoreboard.html",
        context={}
    )

# ==========================================
# SCOREBOARD API
# ==========================================

@app.get("/api/scoreboard")
async def get_scoreboard_api():

    if "current_scoreboard" not in STATE:
        STATE["current_scoreboard"] = {}

    cached = STATE.get("current_scoreboard") or {}

    return {
        "success": True,
        "teams": STATE["flags"],
        "score": cached.get("score", {}),
        "batters": cached.get("batters", []),
        "bowlers": cached.get("bowlers", []),
        "fall_of_wickets": cached.get("fall_of_wickets", []),
        "extras": cached.get("extras", {}),
        "yet_to_bat": cached.get("yet_to_bat", [])
    }
