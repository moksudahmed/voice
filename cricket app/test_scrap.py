from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
import threading
import time
import re
import asyncio
from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright
import random
from commentry import generate_wicket_commentary, generate_winning_commentary, generate_event_commentary,generate_toss_commentary, demonstrate_toss_scenarios, pre_game_scenario_commentary, generate_break_commentary, generate_full_commentary
from game_status import detect_game_status, handle_break_period
from commentry_dic import WELCOME_COMMENTARY_TEMPLATES
from commentry_dic import COMMENTARY
from utill import number_to_bangla_words
import edge_tts
import sounddevice as sd
import soundfile as sf
from fastapi.staticfiles import StaticFiles
from bs4 import BeautifulSoup

app = FastAPI()

# =========================
# TTS ENGINE (WORKING FIX)
# =========================
import pyttsx3

speech_lock = threading.Lock()

def get_bangla_voice(engine):
    voices = engine.getProperty('voices')

    for v in voices:
        name = (v.name or "").lower()
        vid = (v.id or "").lower()

        # Try matching Bengali/Bangla
        if "bengali" in name or "bangla" in name or "bn" in vid:
            return v.id

    return None  # fallback

def speak_bangla(text: str):
    def run():
        with speech_lock:
            try:
                print("🎙 AI SPEAK (BN):", text)

                async def _run():
                    tts = edge_tts.Communicate(
                        text,
                        "bn-BD-NabanitaNeural"   # 🔥 Real Bangla voice
                    )
                    await tts.save("temp_bn.wav")

                asyncio.run(_run())

                data, fs = sf.read("temp_bn.wav")
                sd.play(data, fs)
                sd.wait()

            except Exception as e:
                print("❌ TTS ERROR:", e)

    threading.Thread(target=run, daemon=True).start()


def speak(text: str):
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

    if not obs or scene not in OBS_SCENES or scene == last_scene:
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
    "flags": {
        "team_a_flag": "",
        "team_b_flag": ""
    },
    "data": {
        "team_a": "WAIT",
        "team_b": "SOURCE",
        "score": "0/0",
        "overs": "0.0",
        "status": "STARTING",
        "scene": "LIVE",
        "commentary": "",
        "crr": "0.00",
        "partnership": "0 (0)",
        "striker": "-",
        "striker_runs": 0,
        "striker_balls": 0,
        "non_striker": "-",
        "non_striker_runs": 0,
        "non_striker_balls": 0,
        "bowler": "-",
        "bowler_fig": "0-0 (0)"
    }
}

PREV_DATA = None

# =========================
# TEAM FLAGS SCRAPER (FIXED)
# =========================
   
def extract_team_flags(url):
    result = {
        "team_a_name": "TEAM A",
        "team_b_name": "TEAM B",
        "team_a_flag": "",
        "team_b_flag": ""
    }
    
    
    if not url:
        return result

    try:
        with sync_playwright() as p:
            url = url.rstrip("/") + "/match-details"
            
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            print("🌐 OPENING:", url)
            page.goto(url, timeout=60000)

            # wait main container
            page.wait_for_selector(".team-header-card", timeout=30000)

            # =========================
            # FIX: STRICT SCOPING (IMPORTANT)
            # =========================
            card = page.locator(".team-header-card").first

            # TEAM 1 (LEFT)
            team1 = card.locator(".team1").first
            team1_name = team1.locator(".team-name").inner_text().strip()
            team1_flag = team1.locator("img").get_attribute("src")

            # TEAM 2 (RIGHT)
            team2 = card.locator(".team2").first
            team2_name = team2.locator(".team-name").inner_text().strip()
            team2_flag = team2.locator("img").get_attribute("src")

            browser.close()

            return {
                "team_a_name": team1_name,
                "team_b_name": team2_name,
                "team_a_flag": team1_flag,
                "team_b_flag": team2_flag
            }

    except Exception as e:
        print("❌ FLAG ERROR:", e)
        return result
    
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
    t = text.upper()

    if "WICKET" in t:
        return "REPLAY"
    if "SIX" in t or " 6 " in t:
        return "CROWD"

    return "LIVE"

# =========================
# COMMENTARY GENERATOR
# =========================
def generate_commentary(prev, curr):
    if not prev:
        return "Welcome to the live match!"

    try:
        prev_runs = int(prev["score"].split("/")[0])
        curr_runs = int(curr["score"].split("/")[0])
        diff = curr_runs - prev_runs

        status = curr["status"].upper()

        if "WICKET" in status:
            return "Wicket! Huge breakthrough!"
        elif diff == 6:
            return "Massive six! What a shot!"
        elif diff == 4:
            return "That's a beautiful boundary!"
        elif diff > 0:
            return f"{diff} runs added."
    except:
        pass

    return None

# =========================
# SCRAPER LOOP
# =========================

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

def extract_teams(lines):
    for line in lines:
        if " vs " in line.lower():
            try:
                # Normalize
                line = line.replace(",", "")
                
                # Split by vs
                parts = re.split(r'\bvs\b', line, flags=re.IGNORECASE)

                if len(parts) >= 2:
                    team_a = parts[0].strip()
                    team_b = parts[1].strip().split()[0]  # first word after vs

                    return team_a, team_b

            except Exception as e:
                print("Parse error:", e)

    return None, None
import re

def parse_crex_data(lines):
    data = {
        "team_a": "WAIT",
        "team_b": "SOURCE",
        "score": "0/0",
        "overs": "0.0",
        "status": "LIVE",
        "scene": "LIVE",
        "commentary": "",
        "crr": "0.00",
        "partnership": "0 (0)",
        "striker": "-",
        "striker_runs": 0,
        "striker_balls": 0,
        "non_striker": "-",
        "non_striker_runs": 0,
        "non_striker_balls": 0,
        "bowler": "-",
        "bowler_fig": "0-0 (0)"
    }

    text = " ".join(lines)

    # =========================
    # TEAMS
    # =========================
    for line in lines:
        if " vs " in line.lower():
            parts = re.split(r'\bvs\b', line, flags=re.IGNORECASE)
            if len(parts) >= 2:
                data["team_a"] = parts[0].strip()
                data["team_b"] = parts[1].strip().split()[0]
                break

    # =========================
    # SCORE + OVERS (FIXED)
    # =========================
    score_data = parse_score(text) 
    if score_data: 
        runs, wickets, over, ball = score_data 
        score = f"{runs}/{wickets}" 
        overs = f"{over}.{ball}" 
        data["score"] = f"{runs}/{wickets}"
        data["overs"] = f"{overs}"
    else: 
        score = "0/0" 
        overs = "0.0"
        data["score"] = f"{score}"
        data["overs"] = f"{overs}"
    
   

    # =========================
    # CRR
    # =========================
    crr_match = re.search(r'CRR\s*:\s*([\d\.]+)', text)
    if crr_match:
        data["crr"] = crr_match.group(1)

    # =========================
    # STATUS
    # =========================
    for line in lines:
        if "need" in line.lower() or "opt" in line.lower():
            data["status"] = line
            break

    # =========================
    # PARTNERSHIP
    # =========================
    part_match = re.search(r"P'ship\s*:\s*(\d+\(\d+\))", text)
    if part_match:
        data["partnership"] = part_match.group(1)

    # =========================
    # 🔥 BATSMEN (USING YOUR FUNCTION)
    # =========================
    batsmen = parse_batsmen(text)

    if len(batsmen) >= 1:
        data["striker"] = batsmen[0]["name"]
        data["striker_runs"] = batsmen[0]["runs"]
        data["striker_balls"] = batsmen[0]["balls"]

    if len(batsmen) >= 2:
        data["non_striker"] = batsmen[1]["name"]
        data["non_striker_runs"] = batsmen[1]["runs"]
        data["non_striker_balls"] = batsmen[1]["balls"]

    # =========================
    # 🔥 BOWLER (USING YOUR FUNCTION)
    # =========================
    bowler_data = parse_bowler(text)

    if bowler_data and "bowler" in bowler_data:
        data["bowler"] = bowler_data["bowler"]
        data["bowler_fig"] = f"{bowler_data['wickets']}-{bowler_data['runs_conceded']} ({bowler_data['overs']})"

    return data

def scrape_loop():
    global STATE, PREV_DATA
     
    url = "https://crex.com/cricket-live-score/lsg-vs-mi-47th-match-indian-premier-league-2026-match-updates-118S"
    
    
   
    try:    
            print("Hello")
            data = extract_team_flags(url)
            
            # =========================
            # UPDATE FLAGS
            # =========================
            STATE["flags"] = {
                "team_a_flag": data["team_a_flag"],
                "team_b_flag": data["team_b_flag"]
            }
            print(data)
            STATE["data"]["team_a"] = data["team_a_name"]
            STATE["data"]["team_b"] = data["team_b_name"]

            print("🏏 FLAGS UPDATED:", STATE["flags"])

    except Exception as e:
            print("❌ SCRAPER ERROR:", e)
    while True:
        url = STATE["url"]

        if not url:
            time.sleep(2)
            continue
        
       
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                print("🌐 VISITING:", url)

                page.goto(url, timeout=60000)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(3000)

                text = page.inner_text("body")
                lines = text.splitlines()
                #print(lines)
                # TEAMS
                #team_a = lines[0] if len(lines) > 0 else "TEAM A"
                #team_b = lines[1] if len(lines) > 1 else "TEAM B"
                
                team_a, team_b = extract_teams(lines)
                print(team_a)

                # SCORE
                score_data = parse_score(text)

                if score_data:
                    runs, wickets, over, ball = score_data
                    score = f"{runs}/{wickets}"
                    overs = f"{over}.{ball}"
                else:
                    score = "0/0"
                    overs = "0.0"

                # STATUS
                status = lines[16] if len(lines) > 16 else "LIVE"

                last_status_message =""
                if "CRR" in lines[17]:                                                     
                    last_status_message = lines[16]
                else : 
                    last_status_message = lines[17]
                print(last_status_message)
                has_alpha = any(c.isalpha() for c in last_status_message)

                # ---------------------------------------
                        # PARSE BATSMEN
                        # ---------------------------------------
                batsmen = parse_batsmen(text)
                bowler = parse_bowler(text)
                # SCENE
                scene = scene_logic(text)
                
                message = ""
                if last_status_message and message != last_status_message:
                            
                    if last_status_message == "Ball":  
                        commentary = random.choice(COMMENTARY["BOWLER_RUNUP"]).format(bowler=remove_first_part(clean_name(bowler['bowler'])))                            
                        print(commentary)                       
                        speak_bangla(commentary)

                    elif last_status_message == "0":                       
                        commentary = random.choice(COMMENTARY["DOT"])                           
                        print(commentary)                       
                        speak_bangla(commentary)

                    elif last_status_message == "1":  
                        commentary = random.choice(COMMENTARY["SINGLE"])                          
                        print(commentary)                       
                        speak_bangla(commentary)
                    
                    elif last_status_message == "4":
                        commentary =random.choice(COMMENTARY["FOUR"])
                        print(commentary)                       
                        speak_bangla(commentary)

                    elif last_status_message == "6":
                        commentary =random.choice(COMMENTARY["SIX"])
                        print(commentary)                       
                        speak_bangla(commentary)

                    elif last_status_message == "2":
                        commentary =random.choice(COMMENTARY["DOUBLE"])
                        print(commentary)                       
                        speak_bangla(commentary)
                       
                    elif last_status_message == "Time Out":  
                        commentary = random.choice(COMMENTARY["TIME_OUT"])                            
                        print(commentary)
                        speak_bangla(commentary)
                    elif last_status_message == "Strategic Timeout":  
                        commentary = random.choice(COMMENTARY["STRATEGIC_TIMEOUT"])                            
                        print(commentary)
                        speak_bangla(commentary)
                    message = last_status_message   

                new_data = {
                    "team_a": team_a,
                    "team_b": team_b,
                    "score": score,
                    "overs": overs,
                    "status": status,
                    "scene": scene,
                    "commentary": ""
                }
                status = last_status_message.upper()
                # COMMENTARY + VOICE
                commentary = generate_commentary(PREV_DATA, new_data)

                if commentary:
                    new_data["commentary"] = commentary
                    speak(commentary)   # 🔥 DIRECT CALL (FIXED)
                
                parsed = parse_crex_data(lines)

                STATE["data"] = parsed
                #STATE["data"] = new_data
                PREV_DATA = new_data
                print(STATE["data"])
                switch_scene(scene)

                print("📊 UPDATED:", new_data)

                browser.close()

        except Exception as e:
            print("❌ SCRAPER ERROR:", e)

        time.sleep(2)

# =========================
# INIT
# =========================
init_obs()
threading.Thread(target=scrape_loop, daemon=True).start()

# =========================
# API
# =========================
@app.post("/set-url")
def set_url(payload: dict):
    STATE["url"] = payload.get("url")
    return {"status": "ok"}

app.mount("/static", StaticFiles(directory="static"), name="static")
# =========================
# WEBSOCKET
# =========================
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    print("🔌 WS CONNECTED")

    try:
        while True:
            await websocket.send_json(STATE["data"])
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        print("❌ WS CLOSED")

# =========================
# OVERLAY
# =========================
@app.get("/overlay")
def overlay():
    return FileResponse("templates/overlay.html")

# =========================
# HOME
# =========================
@app.get("/")
def home():
    return HTMLResponse("""
    <html>
    <body style="font-family:Arial;background:#0b1220;color:white;padding:40px">
        <h2>🏏 Cricket AI Broadcast</h2>

        <input id="url" style="width:400px;padding:10px" placeholder="Match URL">
        <button onclick="start()">START</button>

        <p id="msg"></p>

        <script>
        function start(){
            fetch("/set-url", {
                method:"POST",
                headers:{"Content-Type":"application/json"},
                body: JSON.stringify({url: document.getElementById("url").value})
            });
            document.getElementById("msg").innerText = "🚀 Running...";
        }
        </script>
    </body>
    </html>
    """)