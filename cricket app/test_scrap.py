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
from fastapi.middleware.cors import CORSMiddleware
import sounddevice as sd
import soundfile as sf
from fastapi.staticfiles import StaticFiles
from bs4 import BeautifulSoup
from pydantic import BaseModel
from live_players import scrape_players
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# =========================
# TTS ENGINE (WORKING FIX)
# =========================
import pyttsx3

EVENT_STATE = {
    "last_runs": 0,
    "last_wickets": 0,
    "last_event": None
}
# =========================
# GLOBALS
# =========================
FLAGS_LOADED = False
FLAGS_URL = None

speech_lock = threading.Lock()
SCRAPER_RUNNING = False

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
                #print("🎙 AI SPEAK (BN):", text)

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
MATCH_INFO = {
        "series":"",
        "match_info":"",
        "team_info":"",
        "score_info":"",
        "over_info":"",
        "comment":""
    },
STATE = {
    "url": None,
    "flags": {
        "team_a_flag": "",
        "team_b_flag": "",
        "match_info": ""
    },
    "live_players":{
        "name": "",
        "runs": "",
        "balls": "",
        "image": ""
    },
    "match_info":{
        "series":"",
        "match_info":"",
        "team_info":"",
        "score_info":"",
        "over_info":"",
        "comment":""
    },
    "overs_timeline": [],
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
        "bowler_fig": "0-0 (0)",
        "last_status":None,
        # ✅ ADD THESE (EVENT SYSTEM)
        "event": None,
        "event_time": 0
    }
}

PREV_DATA = None

# =========================
# TEAM FLAGS SCRAPER (FIXED)
# =========================
   # =========================
# ASYNC FLAG SCRAPER
# =========================
from playwright.async_api import async_playwright


async def extract_team_flags(url):

    result = {
        "team_a_name": "TEAM A",
        "team_b_name": "TEAM B",
        "team_a_flag": "",
        "team_b_flag": "",
        "match_info": ""
    }

    if not url:
        return result

    browser = None

    try:
        # =========================
        # MATCH DETAILS URL
        # =========================
        url = url.rstrip("/") + "/match-details"

        async with async_playwright() as p:

            browser = await p.chromium.launch(
                headless=True
            )

            page = await browser.new_page()

            print("🌐 OPENING:", url)

            await page.goto(
                url,
                timeout=60000,
                wait_until="domcontentloaded"
            )

            # =========================
            # WAIT FOR CONTENT
            # =========================
            await page.wait_for_selector(
                ".team-header-card",
                timeout=30000
            )

            # =========================
            # EXTRACT MATCH TITLE
            # =========================
            try:
                raw_match_info = await page.locator(
                    ".series-name.mob-none h1.name-wrapper span"
                ).inner_text()

                raw_match_info = raw_match_info.strip()

                # ====================================
                # REMOVE EXTRA TEXT
                # Example:
                # "LSG vs RCB, 50th T20, IPL 2026 Info,
                #  Weather Report, Pitch Report & Playing XI"
                #
                # OUTPUT:
                # "LSG vs RCB, 50th T20, IPL 2026"
                # ====================================

                clean_match_info = re.split(
                    r"\s+Info\s*,|\s+Info\b",
                    raw_match_info,
                    maxsplit=1
                )[0].strip()

                result["match_info"] = clean_match_info

            except Exception as e:
                print("❌ MATCH INFO ERROR:", e)
                result["match_info"] = ""

            # =========================
            # TEAM CARD
            # =========================
            card = page.locator(".team-header-card").first

            # =========================
            # TEAM 1
            # =========================
            team1 = card.locator(".team1").first

            team1_name = (
                await team1.locator(".team-name").inner_text()
            ).strip()

            team1_flag = await team1.locator("img").get_attribute("src")

            # =========================
            # TEAM 2
            # =========================
            team2 = card.locator(".team2").first

            team2_name = (
                await team2.locator(".team-name").inner_text()
            ).strip()

            team2_flag = await team2.locator("img").get_attribute("src")

            # =========================
            # FINAL RESULT
            # =========================
            result.update({
                "team_a_name": team1_name,
                "team_b_name": team2_name,
                "team_a_flag": team1_flag or "",
                "team_b_flag": team2_flag or "",
            })

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
async def extract_team_flags2(url):

    result = {
        "team_a_name": "TEAM A",
        "team_b_name": "TEAM B",
        "team_a_flag": "",
        "team_b_flag": ""
    }

    if not url:
        return result

    try:

        url = url.rstrip("/") + "/match-details"

        async with async_playwright() as p:

            browser = await p.chromium.launch(headless=True)

            page = await browser.new_page()

            print("🌐 OPENING:", url)

            await page.goto(url, timeout=60000)

            # WAIT MAIN CONTAINER
            await page.wait_for_selector(
                ".team-header-card",
                timeout=30000
            )

            # =========================
            # STRICT SCOPING
            # =========================
            card = page.locator(".team-header-card").first

            # =========================
            # TEAM 1
            # =========================
            team1 = card.locator(".team1").first

            team1_name = (
                await team1
                .locator(".team-name")
                .inner_text()
            ).strip()

            team1_flag = await team1.locator("img").get_attribute("src")

            # =========================
            # TEAM 2
            # =========================
            team2 = card.locator(".team2").first

            team2_name = (
                await team2
                .locator(".team-name")
                .inner_text()
            ).strip()

            team2_flag = await team2.locator("img").get_attribute("src")

            await browser.close()

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
# UPDATE FLAGS
# =========================
async def update_team_flags(url):

    """
    Fetch and store team flags asynchronously.
    """

    try:

        data = await extract_team_flags(url)
        
        STATE["flags"] = {
            "team_a_flag": data.get("team_a_flag", ""),
            "team_b_flag": data.get("team_b_flag", ""),
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
        print("Check")
        print(STATE["data"])
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
def generate_commentary2(prev, curr):
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

def get_milestone_comment(name, runs):
    """Return milestone commentary for 50/100 runs."""
    if runs == 50:
        return f"🎉 কী দুর্দান্ত ব্যাটিং! {name} এখন হাফ সেঞ্চুরি (৫০ রান) পূর্ণ করেছে!"
    elif runs == 100:
        return f"🔥 অসাধারণ ইনিংস! {name} সেঞ্চুরি (১০০ রান) পূর্ণ করেছে! গ্যালারি উল্লাসে ফেটে পড়ছে!"
    return None

def generate_continuous_commentary(events, batsmen, bowler, score, team1=None, team2=None, context=None):
    """
    Generate a smooth, human-like cricket commentary for a sequence of events
    - events: list of strings (SIX, FOUR, WICKET, DOUBLE, SINGLE, DOT, WIDE, NO_BALL, OVER_COMPLETE)
    - batsmen: list of dicts [{'name':str,'runs':int}, ...]
    - runs: total runs
    - wickets: total wickets
    - over: current over (float)
    - team1, team2: optional team names for updates
    """
    has_alpha = any(c.isalpha() for c in context)
    #has_digit = any(c.isdigit() for c in context)
    runs, wickets, over, ball = score
    status = None
    if has_alpha:
        status = context
        print("Context", context)
    
    
    parts = []

    # 1️⃣ WICKET has highest priority
    if "WICKET" in events:
        parts.append(generate_wicket_commentary(runs, wickets, over, batsmen[0]['name'] if batsmen else None, context))

    # 2️⃣ Scoring events (SIX, FOUR, DOUBLE, SINGLE, DOT)
    scoring_priority = ["SIX", "FOUR", "DOUBLE", "SINGLE", "DOT"]
    for event in scoring_priority:
        if event in events:        
            parts.append(generate_event_commentary([event]))            
            break  # Only one scoring commentary per ball

    # 3️⃣ Extras
    for extra in ["WIDE", "NO_BALL"]:
        if extra in events:
            parts.append(generate_event_commentary([extra]))

    # 4️⃣ Batsman status
    if batsmen and len(batsmen) >= 2:
        b1 = batsmen[0]
        b2 = batsmen[1]

        # Basic score update commentary
        parts.append(
            f"{b1['name']} এখন {number_to_bangla_words(b1['runs'])} রান করছে, "
            f"{b2['name']} করছে {number_to_bangla_words(b2['runs'])} রান।"
        )

        # Check milestones for both batsmen
        for b in [b1, b2]:
            milestone_comment = get_milestone_comment(b["name"], b["runs"])
            if milestone_comment:
                parts.append(milestone_comment)
    elif batsmen and len(batsmen) == 1:
        b1 = batsmen[0]
        parts.append(f"{b1['name']} এখন {number_to_bangla_words(b1['runs'])} রান করছে।")

    # 5️⃣ Over complete summary
    if "OVER_COMPLETE" in events:
        over_comment = ""
        if context == "MAIDEN OVER":
            commentary_text = random.choice(COMMENTARY["MAIDEN_OVER"])
            over_comment = commentary_text + f"{number_to_bangla_words(over)} ওভার শেষ। স্কোর এখন {number_to_bangla_words(runs)} রান, {number_to_bangla_words(wickets)} উইকেট।"
        else:
            over_comment = f"{number_to_bangla_words(over)} ওভার শেষ। স্কোর এখন {number_to_bangla_words(runs)} রান, {number_to_bangla_words(wickets)} উইকেট।"
        parts.append(over_comment)
        
        # 6️⃣ Welcome message and quick update for new viewers
        if team1 and team2:
            welcome_msg = (
                f"যারা নতুন যুক্ত হয়েছেন, স্বাগতম! "
                f"এই সময় {team1} বনাম {team2} ম্যাচে স্কোর {number_to_bangla_words(runs)} রানে {number_to_bangla_words(wickets)} উইকেট। "
                f"{number_to_bangla_words(over)} ওভার শেষ হয়েছে, দলের সংগ্রহ ভালোভাবে এগুচ্ছে। ম্যাচে উত্তেজনা অব্যাহত!"
            )
            parts.append(welcome_msg)     

    # Combine all commentary parts naturally
    return " ".join(parts)

def generate_commentary(events, batsmen, bowler, score, team1=None, team2=None, context=None):
    events = (events or "").strip()
    runs, wickets, over, ball = score
    # Normalize keys
    mapping = {
        "Ball": "BOWLER_RUNUP",
        "0": "DOT",
        "1": "SINGLE",
        "2": "DOUBLE",
        "4": "FOUR",
        "6": "SIX",
        "Time Out": "TIME_OUT",
        "Strategic Timeout": "STRATEGIC_TIMEOUT"
    }

    key = mapping.get(events)

    if not key or key not in COMMENTARY:
        return None  # safe fallback

    template = random.choice(COMMENTARY[key])

    # Handle special formatting (bowler)
    if key == "BOWLER_RUNUP" and bowler:
        try:
            name = remove_first_part(clean_name(bowler.get("bowler", "")))
            return template.format(bowler=name)
        except:
            return template

    return template              
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

import re

def parse_overs(text):
    overs_data = []

    # Split by "Over X"
    pattern = r"Over\s+(\d+)(.*?)(?=Over\s+\d+|Projected Score|Commentary|$)"
    matches = re.findall(pattern, text, re.S)

    for over_no, content in matches:
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip()
        ]

        balls = []
        total = None

        for line in lines:

            # Skip total line
            if "=" in line:
                total_match = re.search(r"=\s*(\d+)", line)
                if total_match:
                    total = int(total_match.group(1))
                continue

            # Valid ball events
            valid = [
                "0", "1", "2", "3", "4", "5", "6",
                "W", "wd", "nb", "lb", "b"
            ]

            if line in valid:
                balls.append(line)

        overs_data.append({
            "over": int(over_no),
            "balls": balls,
            "total": total
        })

    return overs_data

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
        
def parse_batsmen2(text):
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
def parse_batsmen(html):
    """
    Extract exactly 2 batsmen (name, runs, balls, image)
    """

    html = html.replace("\r", "").strip()

    # remove noise
    remove_words = [
        "Match info", "Live", "Scorecard",
        "Commentary", "Over", "Projected Score"
    ]
    for w in remove_words:
        html = html.replace(w, "")

    result = []

    # ✅ STEP 1: get full batsman blocks safely
    blocks = re.findall(
        r'<div[^>]*class="batsmen-partnership"[\s\S]*?(?=<div[^>]*class="batsmen-partnership"|</div>\s*</div>\s*</div>)',
        html
    )

    for block in blocks:

        # -------------------------
        # NAME (main displayed name)
        # -------------------------
        name_match = re.search(
            r'class="batsmen-name"[\s\S]*?<p[^>]*>(.*?)</p>',
            block
        )

        # -------------------------
        # RUNS + BALLS
        # -------------------------
        score_match = re.search(
            r'class="batsmen-score"[\s\S]*?<p[^>]*>(\d+)</p>\s*<p[^>]*>\((\d+)\)</p>',
            block
        )

        # -------------------------
        # IMAGE (FIXED - correct scope)
        # -------------------------
        img_match = re.search(
            r'class="batsmen-image"[\s\S]*?<img[^>]+src="([^"]+cricketvectors[^"]+)"',
            block
        )

        if name_match and score_match:

            name = remove_first_part(clean_name(name_match.group(1)))
            runs = int(score_match.group(1))
            balls = int(score_match.group(2))

            image = img_match.group(1) if img_match else None
            print(image)
            result.append({
                "name": name,
                "runs": runs,
                "balls": balls,
                "image": image
            })
            print(result)
        if len(result) == 2:
            break

    return result

def parse_crex_data(lines):
    data = {
        "team_a": STATE["data"].get("team_a", "WAIT"),
        "team_b": STATE["data"].get("team_b", "SOURCE"),
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
    """for line in lines:
        if " vs " in line.lower():
            parts = re.split(r'\bvs\b', line, flags=re.IGNORECASE)
            if len(parts) >= 2:
                data["team_a"] = parts[0].strip()
                data["team_b"] = parts[1].strip().split()[0]
                break"""

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

# =====================================================
# 🎯 EVENT MAPS (FAST LOOKUP)
# =====================================================
RUN_EVENT_MAP = {
    "0": "DOT",
    "1": "SINGLE",
    "2": "DOUBLE",
    "3": "TRIPLE",
    "4": "FOUR",
    "6": "SIX",
    "Wide": "WIDE",
    "No Ball": "NO_BALL",
    "Bye": "BYE",
    "Wicket": "WICKET",
    "Over": "OVER_COMPLETE"
}

EXTRA_EVENT_MAP = {
    "Wide": "WIDE",
    "No Ball": "NO_BALL",
    "Bye": "BYE"
}

BREAK_EVENT_MAP = {
    "Innings Break": "INNINGS_BREAK",
    "Drinks Break": "DRINKS_BREAK",
    "Tea Break": "TEA_BREAK",
    "Lunch Break": "LUNCH_BREAK",
    "Rain Break": "RAIN_BREAK",
    "Rain Break (Delayed)": "RAIN_DELAY"
}
# =====================================================
# 🎯 EVENT DETECTION (FAST)
# =====================================================
# =====================================================
# 🎯 EVENT DETECTION (FAST + SAFE FALLBACK)
# =====================================================

def detect_event(event):

    # normalize input (helps avoid mismatch like "wide " or "WIDE")
    if event is None:
        return "UNKNOWN_EVENT"

    key = str(event).strip()

    # priority order: RUN → EXTRA → BREAK
    return (
        RUN_EVENT_MAP.get(key)
        or EXTRA_EVENT_MAP.get(key)
        or BREAK_EVENT_MAP.get(key)
        or "UNKNOWN_EVENT"
    )
def detect_run_event(event):
    if event == "6":
        return "SIX"
    elif event == "4":
        return "FOUR"
    elif event == "Wicket":
        return "WICKET"
    else: return None

def get_over_before_crr(lines):
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

def game_engine():
    #global STATE, PREV_DATA
    global STATE, PREV_DATA, SCRAPER_RUNNING
    
    
    while True:
        url = STATE["url"]

        # 🛑 HARD STOP
        if not SCRAPER_RUNNING:
            time.sleep(1)
            continue

        if not url:
            time.sleep(2)
            continue     
       

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                print("🌐 VISITING:", url)
                
                page.goto(url, timeout=60000)
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(3000)
                
                # ✅ GET FULL HTML
                #scrape_players(url)
                text = page.inner_text("body")
                lines = text.splitlines()
                
                # TEAMS
                #team_a = lines[0] if len(lines) > 0 else "TEAM A"
                #team_b = lines[1] if len(lines) > 1 else "TEAM B"
                
                #team_a, team_b = extract_teams(lines)
                
                

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
                """if "CRR" in lines[17]:                                                     
                    last_status_message = lines[16]
                else : 
                    last_status_message = lines[17]"""
                last_status_message = get_over_before_crr(lines)
                
                
                has_alpha = any(c.isalpha() for c in last_status_message)

                # ---------------------------------------
                        # PARSE BATSMEN
                        # ---------------------------------------
                batsmen = parse_batsmen(text)
                bowler = parse_bowler(text)
                # SCENE
                scene = scene_logic(text)
                
                events = detect_event(last_status_message)
                if not events:
                    #time.sleep(REFRESH_INTERVAL)
                    continue
                print("Hello Check")
                print(score_data)  
                print("EVENTS:", events)
                #commentary = generate_commentary(last_status_message, batsmen, bowler, score_data, team_a, team_b)
                commentary = generate_continuous_commentary(events, batsmen, bowler, score_data, STATE["data"]["team_a"], STATE["data"]["team_b"], last_status_message)
                #speak_bangla(commentary)    
                if commentary:
                    speak_bangla(commentary) 
                    #print(commentary)
                """if last_status_message and message != last_status_message:
                            
                    #commentary = generate_commentary(last_status_message, bowler, batsmen)
                    #if commentary:
                    #    speak_bangla(commentary) 
                    print(commentary)
                    #speak_bangla(commentary)
                    message = last_status_message   """

                new_data = {                    
                    "score": score,
                    "overs": overs,
                    "status": status,
                    "scene": scene,
                    "commentary": ""
                }
                status = last_status_message.upper()
                # COMMENTARY + VOICE
                #speak(commentary)   # 🔥 DIRECT CALL (FIXED)
                
                parsed = parse_crex_data(lines)

                STATE["data"] = parsed
                #STATE["data"] = new_data
                PREV_DATA = new_data

                overs_timeline = parse_overs(text)
                print("Check Message")
                print(last_status_message)

                STATE["data"]["overs_timeline"] = overs_timeline

                #STATE["data"]["last_status"] = last_status_message
                STATE["data"]["commentary"] = last_status_message
                print(STATE["data"]["commentary"])
                STATE["data"]["event"] = detect_run_event(last_status_message)     
                #print(STATE)
                # =========================
                # 🔥 EVENT DETECTION (CRITICAL FIX)
                # =========================                
                parsed["event_time"] = int(time.time() * 1000)
                
                switch_scene(scene)
                # =========================
                # 🎬 OBS SCENE SWITCH
                # =========================
                if last_status_message == "SIX":
                    switch_scene("CROWD")
                elif last_status_message == "FOUR":
                    switch_scene("REPLAY")               

                #print(STATE)

                print("📊 UPDATED:", new_data)

                browser.close()

        except Exception as e:
            print("❌ SCRAPER ERROR:", e)

        time.sleep(2)


# =========================
# SCRAPER FUNCTION
# =========================

# =========================
# REQUEST MODEL
# =========================
class UrlRequest(BaseModel):
    url: str | None = None

async def get_live_matches():
    matches = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        CREX_URL = "https://crex.com/cricket-live-score"
        
        await page.goto(CREX_URL, timeout=60000)
        await page.wait_for_timeout(5000)  # allow JS load

        # match cards (CREX structure)
        #cards = await page.locator(".match-card, .match-box, .scorecard, a").all()
        cards = await page.locator("app-live-matches .live-card").all()
        print(cards)
        for card in cards:
            try:
                text = await card.inner_text()

                # filter only live matches
                if "LIVE" in text.upper() or "STUMPS" in text.upper():

                    teams = await card.locator("text=/vs/i").all_inner_texts()

                    link = await card.get_attribute("href")
                    if link and link.startswith("/"):
                        link = "https://crex.com" + link

                    matches.append({
                        "text": text.strip(),
                        "url": link
                    })

            except:
                continue

        await browser.close()

    return matches

async def get_live_matches():
    matches = []

    CREX_URL = "https://crex.com/cricket-live-score"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(CREX_URL, timeout=60000)
        await page.wait_for_timeout(6000)  # wait Angular render

        # =========================
        # LIVE MATCH CARDS
        # =========================
        cards = await page.locator("div.live-card").all()

        for card in cards:
            try:
                # =========================
                # CHECK LIVE STATUS
                # =========================
                live_tag = await card.locator(".liveTag").all_inner_texts()
                if not any("live" in t.lower() for t in live_tag):
                    continue

                # =========================
                # SERIES NAME (TOP)
                # =========================
                series = await card.locator("h2.snameTag").first.inner_text()
                series = series.strip() if series else "Live Match"

                # =========================
                # MATCH URL (MAIN LINK)
                # =========================
                match_link_el = card.locator(
                    "a[href*='cricket-live-score'], a[href*='match-updates']"
                ).last

                href = await match_link_el.get_attribute("href")

                if href and href.startswith("/"):
                    href = "https://crex.com" + href

                # =========================
                # MATCH TITLE / INFO
                # =========================
                match_info = await card.locator("h3.match-number").first.inner_text()
                match_info = match_info.strip() if match_info else ""

                # =========================
                # COMMENT (IMPORTANT INFO)
                # =========================
                comment = await card.locator(".comment").first.inner_text()
                comment = comment.strip() if comment else ""

                # =========================
                # TEAMS + SCORES
                # =========================
                teams = await card.locator(".team-name").all_inner_texts()
                scores = await card.locator(".team-score").all_inner_texts()
                overs = await card.locator(".match-over").all_inner_texts()

                team_info = ""
                if len(teams) >= 2:
                    team_info = f"{teams[0]} vs {teams[1]}"

                score_info = ""
                if scores:
                    score_info = " | ".join([s.strip() for s in scores if s.strip()])

                over_info = ""
                if overs:
                    over_info = "Overs: " + " | ".join(overs)

                # =========================
                # FINAL FORMAT
                # =========================
                text = "\n".join(filter(None, [
                    series,
                    match_info,
                    team_info,
                    score_info,
                    over_info,
                    comment
                ]))
                # =========================
                # STATE SAVE (FIXED)
                # =========================
                MATCH_INFO = {
                    "series": series,
                    "match_info": match_info,
                    "team_info": team_info,
                    "score_info": score_info,
                    "over_info": over_info,
                    "comment": comment,
                    "url": href
                }
                print("Check State")
                print(MATCH_INFO)
                matches.append({
                    "text": text,
                    "url": href
                })

            except Exception as e:
                print("❌ CARD ERROR:", e)
                continue

        await browser.close()

    return matches
# =========================
# INIT
# =========================
init_obs()
threading.Thread(target=game_engine, daemon=True).start()

# =========================
# API
# =========================

@app.post("/set-url")
def set_url(payload: dict):
    global SCRAPER_RUNNING

    url = payload.get("url")

    STATE["url"] = url

    if url:
        SCRAPER_RUNNING = True
        print("▶ SCRAPER STARTED")
    else:
        SCRAPER_RUNNING = False
        print("⏹ SCRAPER STOPPED")

    return {"status": "ok"}

app.mount("/static", StaticFiles(directory="static"), name="static")

# =========================
# OVERLAY
# =========================
@app.get("/overlay")
def overlay():
    return FileResponse("templates/overlay.html")

# =========================
# HOME PAGE (UI)
# =========================
@app.get("/")
def home():
    return FileResponse("templates/home.html")


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


# =========================
# START / STOP API
# =========================
@app.post("/set-url")
def set_url(payload: dict):
    global SCRAPER_RUNNING

    STATE["url"] = payload.get("url")

    if STATE["url"]:
        SCRAPER_RUNNING = True
    else:
        SCRAPER_RUNNING = False

    return {"status": "ok", "running": SCRAPER_RUNNING}

# =========================
# STOP MATCH
# =========================

@app.post("/stop")
def stop():
    global SCRAPER_RUNNING

    SCRAPER_RUNNING = False

    STATE["data"]["status"] = "STOPPED"
    STATE["data"]["event"] = None

    return {"status": "stopped"}

# WEBSOCKET (🔥 FIXED STRUCTURE)
# =========================
@app.websocket("/ws")
async def ws(websocket: WebSocket):

    await websocket.accept()

    print("🔌 WS CONNECTED")

    try:

        # =========================
        # LOAD FLAGS ONLY ONCE
        # =========================
        await ensure_flags_loaded()

        while True:

            # =========================
            # LIVE PLAYERS
            # =========================
            live_players = await scrape_players(
                STATE["url"]
            )
            print("Check State")
            print(MATCH_INFO)
            # =========================
            # SEND DATA
            # =========================
            await websocket.send_json({

                **STATE["data"],

                "flags": STATE["flags"],

                "live_players": live_players,
                "match_info": MATCH_INFO
            })

            await asyncio.sleep(1)

    except WebSocketDisconnect:

        print("❌ WS CLOSED")