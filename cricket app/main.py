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
from player_list import get_playing_xi, generate_team_html
from commentry import generate_continuous_commentary, bangla_commentary, generate_full_commentary
from bangla_commentry import generate_current_match_status
from game_status import detect_game_status, handle_break_period, detect_live_status
from commentry_dic import WELCOME_COMMENTARY_TEMPLATES
from commentry_dic import COMMENTARY, EXTRA_COMMENTARY
from fastapi.templating import Jinja2Templates
from utill import number_to_bangla_words
import re
from obs_config import switch_scene, init_obs
from pydantic import BaseModel
from voice import speak_bangla, stop_current_tts, reset_stop_flag
from scraper import scrap_page
from live_matches import get_live_matches
from live_status import detect_match_event, get_event_string
from run_events import detect_event, detect_event_advanced ,EVENT_MAP

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
    "url": "",
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
    "data": {}
}

match_state = {
    "team_a": "",
    "team_b": "",

    "batting_team": "",
    "bowling_team": "",

    "innings": 1
}
clients = set()
# =========================
# GLOBALS
# =========================
FLAGS_LOADED = False
FLAGS_URL = None
STOP_ENGINE = False
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
    "Bowled": "WICKET",
    "Caught Out":"WICKET",
    "Run Out": "WICKET",
    "Bowler Stopped":"",
    "Run Out Check":"",
    "Boundary Check":"",
    "Over": "OVER_COMPLETE"
}

EXTRA_EVENT_MAP = {
    "Ball":"BOWLER_RUNUP",
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
    "Rain Break (Delayed)": "RAIN_DELAY",
    "Match stopped due to rain":"RAIN_BREAK",
    "Time Out": "TIME_OUT",
    "Strategic Timeout": "STRATEGIC_TIMEOUT"

}
# =====================================================
# 🎯 EVENT DETECTION (FAST)
# =====================================================


def generate_welcome_message(team1, team2):
    template = random.choice(WELCOME_COMMENTARY_TEMPLATES)
    return template.format(team1=team1, team2=team2)


# =====================================================
# 🎯 EVENT DETECTION (FAST + SAFE FALLBACK)
# =====================================================

def detect_event2(event):

    # normalize input (helps avoid mismatch like "wide " or "WIDE")
    if event is None:
        return "UNKNOWN_EVENT"

    key = str(event).strip()

    # priority order: RUN → EXTRA → BREAK
    return (
        RUN_EVENT_MAP.get(key)
        or EXTRA_EVENT_MAP.get(key)
        #or BREAK_EVENT_MAP.get(key)
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
        
def process_event(res):    
    event_key=""
    result = res.lower()
    event = detect_event(result)
    print("Basic",event)
    if event == "UNKNOWN_EVENT":
        event = detect_event_advanced(result)        
        print("Advance",event)
        if event == "UNKNOWN_EVENT":
           event_key = detect_match_event(result)                   
           print("Match Status",event_key)
           return event_key
        return event    
    else:
        return event
        
async def scraper():

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()
    innings_state = False
    last_state = None
    last_event = ""
    match_title=""
    current_status = "Live"
    print("Start Scraping")
    while True:

        try:

            if not STATE["url"]:
                await asyncio.sleep(0.15)
                continue

            # =====================================================
            # FIRST LOAD ONLY
            # =====================================================
            if not STATE["connected"]:

                await page.goto(
                    STATE["url"],
                    wait_until="domcontentloaded"
                )

                await page.wait_for_timeout(2000)

                # 🔥 fast mutation flag
                await page.evaluate("""
                    window.__dirty = true;

                    const obs = new MutationObserver(() => {
                        window.__dirty = true;
                    });

                    obs.observe(document.body, {
                        childList: true,
                        subtree: true,
                        characterData: true
                    });
                """)

                STATE["connected"] = True

            # =====================================================
            # SKIP IF NO CHANGE
            # =====================================================
            if not await page.evaluate("window.__dirty"):
                await asyncio.sleep(0.12)
                continue

            await page.evaluate("window.__dirty = false")

            # =====================================================
            # 🔥 FULL HYBRID DOM + TEXT ENGINE
            # =====================================================
            # =====================================================
            # 🔥 FULL HYBRID DOM + TEXT ENGINE (REWRITTEN)
            # =====================================================

            parsed = await scrap_page(page)
            # =====================================================
            # SEND ONLY IF CHANGED (FAST HASH STYLE OPTIONAL)
            # =====================================================
          
            # Extract match data for live matches
            status =""
            event_key = None
            commentary_text =None
            status=None
            event=None
            print("*******")
            result=""
            if "Live" in current_status:
                # parse result
                result = parsed["result_boxes"][0]
                event_key = process_event(result)
                if event_key in list(EXTRA_COMMENTARY.values()):
                        commentary_text = random.choice(EXTRA_COMMENTARY[event_key])
                        speak_bangla(commentary_text) 
                if event_key:                 
                    if parsed != last_state:
                        last_state = parsed
                        STATE["data"] = parsed
                       
                        batsman = parse_batsmen(parsed)
                        
                        bowler = parse_bowler(parsed["live_players"]['bowler'])                          
                        print("batsman", batsman)
                        full_over = int(parsed["overs"].split(".")[0])
                        #STATE["data"]["result_boxes"] = "4"
                        if event_key != last_event:                           
                            print("check",result)
                            print(event_key)
                            teamA = STATE["flags"].get("team_a_bangla_name") or STATE["flags"].get("team_a_full_name") or STATE["flags"].get("team_a_name") or "TEAM A"
                            teamB = STATE["flags"].get("team_b_bangla_name") or STATE["flags"].get("team_b_full_name") or STATE["flags"].get("team_b_name") or "TEAM B"
                            
                            commentary = generate_continuous_commentary(event_key, batsman, bowler, parsed["score"], 
                                                                            full_over, teamA, 
                                                                            teamB, event_key)
                            
                            
                            if commentary:
                                
                                STATE["data"]["commentary"] = commentary
                                
                                speak_bangla(commentary) 
                                print(commentary)
                            
                                
                            if event_key == "INNINGS_BREAK":
                                swap_teams(STATE["flags"])
                            
                            last_event = event_key
                            
                        dead = []
                        
                        
                        for ws in list(clients):
                            try:
                            # await ws.send_json(parsed)
                                await ws.send_json({
                                    **STATE["data"],
                                    "flags": STATE["flags"]
                                })
                            except:
                                dead.append(ws)

                        for d in dead:
                            clients.remove(d)
                
                    #print("📡 UPDATE:", parsed["score"], parsed["overs"])
                """else:
                    try:
                        # Safe fetch from dictionary
                        commentary_list = EXTRA_COMMENTARY.get(event_key)

                        if commentary_list and len(commentary_list) > 0:
                            commentary_text = random.choice(commentary_list)
                        else:
                            commentary_text = f"📢 {event_key}"  # fallback if no commentary available

                        print(commentary_text)
                        speak_bangla(commentary_text)
                        commentary_text=""
                        
                    except Exception as e:
                        print("❌ ERROR TYPE:", type(e).__name__)
                        print("❌ ERROR:", str(e))
                        print("❌ EVENT KEY:", repr(event_key))

                        # Safe fallback so system never breaks
                        fallback_text = f"📢 {status}"
                        print(fallback_text)
                        speak_bangla(fallback_text)
          
                    
                    #commentary =  bangla_commentary(data)"""
            
            # 9. Unknown status
            #if "Unknown" in current_status:
            #    print("⚠️ Could not determine match status. Exiting.")
                
            await asyncio.sleep(0.12)
        
        except KeyboardInterrupt:
                print("\n👋 Manual stop requested. Exiting gracefully...")                
        except Exception as e:
            print("❌ SCRAPER ERROR:", e)
            STATE["connected"] = False
            await asyncio.sleep(2)

async def scraper2():

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()
    innings_state = False
    last_state = None
    last_event = ""
    match_title=""
    current_status = "Live"
    print("Start Scraping")
    while True:

        try:

            if not STATE["url"]:
                await asyncio.sleep(0.15)
                continue

            # =====================================================
            # FIRST LOAD ONLY
            # =====================================================
            if not STATE["connected"]:

                await page.goto(
                    STATE["url"],
                    wait_until="domcontentloaded"
                )

                await page.wait_for_timeout(2000)

                # 🔥 fast mutation flag
                await page.evaluate("""
                    window.__dirty = true;

                    const obs = new MutationObserver(() => {
                        window.__dirty = true;
                    });

                    obs.observe(document.body, {
                        childList: true,
                        subtree: true,
                        characterData: true
                    });
                """)

                STATE["connected"] = True

            # =====================================================
            # SKIP IF NO CHANGE
            # =====================================================
            if not await page.evaluate("window.__dirty"):
                await asyncio.sleep(0.12)
                continue

            await page.evaluate("window.__dirty = false")

            # =====================================================
            # 🔥 FULL HYBRID DOM + TEXT ENGINE
            # =====================================================
            # =====================================================
            # 🔥 FULL HYBRID DOM + TEXT ENGINE (REWRITTEN)
            # =====================================================

            parsed = await scrap_page(page)
            # =====================================================
            # SEND ONLY IF CHANGED (FAST HASH STYLE OPTIONAL)
            # =====================================================
          
            # Extract match data for live matches
            status =""
            event_key = None
            commentary_text =None
            status=None
            event=None
            print("*******")
            result=""
            if "Live" in current_status:
                # parse result
                result = parsed["result_boxes"][0]
                process_event(result)
                event = detect_event(result)
                
                if event == "UNKNOWN_EVENT":
                    event = detect_event_advanced(result)
                print("check event", event)
                #data = parse_match_result(parsed["result_boxes"][0])
                print("Event", event)
                if event == "UNKNOWN_EVENT":
                    event_key = get_event_key(result)
                    
                    print("Event key", event_key)
                    #status = get_event_string(event_key)
                    if event_key:
                        status = get_event_string(event_key)
                        if status:

                            try:
                                # Safe fetch from dictionary
                                commentary_list = EXTRA_COMMENTARY.get(event_key)

                                if commentary_list and len(commentary_list) > 0:
                                    commentary_text = random.choice(commentary_list)
                                else:
                                    commentary_text = f"📢 {status}"  # fallback if no commentary available

                                print(commentary_text)
                                speak_bangla(commentary_text)
                                commentary_text=""
                                
                            except Exception as e:
                                print("❌ ERROR TYPE:", type(e).__name__)
                                print("❌ ERROR:", str(e))
                                print("❌ EVENT KEY:", repr(event_key))

                                # Safe fallback so system never breaks
                                fallback_text = f"📢 {status}"
                                print(fallback_text)
                                speak_bangla(fallback_text)
                  
                            
                            #commentary =  bangla_commentary(data)
                    
                            
                
                else:
                    if parsed != last_state:
                        last_state = parsed
                        STATE["data"] = parsed
                        

                        # scraped text
                        #text = "Dragons Women won by 8 runs 🏆"

                        
                        
                        #commentary= bangla_commentary(event)
                        #STATE["data"]["commentary"]= event
                        #batsmen = parsed["result_boxes"][0]
                    
                        batsman = parse_batsmen(parsed)
                        
                        bowler = parse_bowler(parsed["live_players"]['bowler'])                         
                        
                        full_over = int(parsed["overs"].split(".")[0])
                        #STATE["data"]["result_boxes"] = "4"
                        if event != last_event:
                            

                            teamA = STATE["flags"].get("team_a_bangla_name") or STATE["flags"].get("team_a_full_name") or STATE["flags"].get("team_a_name") or "TEAM A"
                            teamB = STATE["flags"].get("team_b_bangla_name") or STATE["flags"].get("team_b_full_name") or STATE["flags"].get("team_b_name") or "TEAM B"
                            
                            commentary = generate_continuous_commentary(event, batsman, bowler, parsed["score"], 
                                                                            full_over, teamA, 
                                                                            teamB, event)
                            
                            
                            if commentary:
                                
                                STATE["data"]["commentary"] = commentary
                                
                                speak_bangla(commentary) 
                                print(commentary)
                            last_event = event
                        dead = []
                        
                        
                        for ws in list(clients):
                            try:
                            # await ws.send_json(parsed)
                                await ws.send_json({
                                    **STATE["data"],
                                    "flags": STATE["flags"]
                                })
                            except:
                                dead.append(ws)

                        for d in dead:
                            clients.remove(d)
                
                    #print("📡 UPDATE:", parsed["score"], parsed["overs"])
                
            
            # 9. Unknown status
            #if "Unknown" in current_status:
            #    print("⚠️ Could not determine match status. Exiting.")
                
            await asyncio.sleep(0.12)
        
        except KeyboardInterrupt:
                print("\n👋 Manual stop requested. Exiting gracefully...")                
        except Exception as e:
            print("❌ SCRAPER ERROR:", e)
            STATE["connected"] = False
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
    if action and action in ["WAIT", "LIVE", "COMPLETE", "STOP", "PAUSE", "ERROR", "UNKNOWN", "REFRESH"]:
        asyncio.create_task(voice_announce_once(action, status, message))
    
    return {
        "success": success,
        "status": status,
        "message": message,
        "action": action,
        "data": data or {}
    }

async def run_ai_engine():
    """
    Scrape match page and return status information
    suitable for frontend consumption.
    """

    playwright = None
    browser = None

    url = STATE.get("url")

    if not url:
        return api_response(
            success=False,
            status="Invalid URL",
            message="No match URL found."
        )

    try:
        playwright = await async_playwright().start()

        browser = await playwright.chromium.launch(
            headless=True
        )

        page = await browser.new_page()

        print(f"🌐 Opening: {url}")

        await page.goto(url, timeout=60000)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3000)

        print("🚀 SYSTEM STARTED...")

        text = await page.inner_text("body")
        lines = text.splitlines()

        status = detect_game_status(lines)

        print(f"📊 Current Status: {status}")

        # ==================================================
        # ABANDONED
        # ==================================================

        if "Abandoned" in status:           
            return api_response(
                status=status,
                message="Match has been abandoned.",
                action="STOP"
            )

        # ==================================================
        # SUSPENDED / DEFERRED
        # ==================================================

        if "Suspended" in status or "Deferred" in status:
            return api_response(
                status=status,
                message=f"Match is currently {status}.",
                action="PAUSE"
            )

        # ==================================================
        # COMPLETED
        # ==================================================

        if "Completed" in status:

            result_text = status.replace("Completed - ", "")

            return api_response(
                status=status,
                message=f"Match finished. {result_text}",
                action="COMPLETE",
                data={
                    "result": result_text
                }
            )

        # ==================================================
        # TOMORROW
        # ==================================================

        if "Tomorrow" in status:
            return api_response(
                status=status,
                message="Match is scheduled for tomorrow.",
                action="WAIT"
            )

        # ==================================================
        # TODAY AT SPECIFIC TIME
        # ==================================================

        if "Today at" in status:

            time_match = re.search(
                r'(\d{1,2}:\d{2}\s*(?:AM|PM))',
                status
            )

            if time_match:

                match_time_str = time_match.group(1)

                now = datetime.now()

                match_time = datetime.strptime(
                    match_time_str,
                    "%I:%M %p"
                )

                match_time = now.replace(
                    hour=match_time.hour,
                    minute=match_time.minute,
                    second=0,
                    microsecond=0
                )

                if now > match_time:

                    await page.reload()
                    await page.wait_for_timeout(2000)

                    text = await page.inner_text("body")
                    lines = text.splitlines()

                    updated_status = detect_game_status(lines)

                    return api_response(
                        status=updated_status,
                        message=f"Status updated: {updated_status}",
                        action="REFRESH"
                    )

                wait_seconds = (
                    match_time - now
                ).total_seconds()

                return api_response(
                    status=status,
                    message=f"Match starts at {match_time_str}",
                    action="WAIT",
                    data={
                        "wait_seconds": int(wait_seconds)
                    }
                )

        # ==================================================
        # SCHEDULED
        # ==================================================

        if "Scheduled" in status:

            return api_response(
                status=status,
                message="Match has not started yet.",
                action="WAIT"
            )

        # ==================================================
        # YET TO START
        # ==================================================

        if "Yet to Start" in status:

            return api_response(
                status=status,
                message="Waiting for toss or match start.",
                action="WAIT"
            )

        # ==================================================
        # LIVE / BREAK
        # ==================================================
       
        print(status)
        if "Live" in status or "Break" in status:

            print("🎬 MATCH IS LIVE")

            # Run scraper in background
            #asyncio.create_task(scraper())
            await scraper()
            """return api_response(
                status=status,
                message="Live match detected. Monitoring started.",
                action="LIVE"
            )"""
        
        if "Stoped" in status :

            print("🎬 Match Stoped")

            # Run scraper in background          

            return api_response(
                status=status,
                message="Match stopped due to rain",
                action="LIVE"
            )
        # ==================================================
        # UNKNOWN
        # ==================================================

        return api_response(
            status=status,
            message="Unable to determine match state.",
            action="UNKNOWN",
            success=False
        )

    except Exception as e:

        print(f"❌ ERROR in run_ai_engine: {e}")

        return api_response(
            success=False,
            status="Error",
            message=str(e),
            action="ERROR"
        )

    finally:

        if browser:
            await browser.close()

        if playwright:
            await playwright.stop()


async def run_ai_engine_old():
    """
    Playwright scraping engine with safe URL validation.
    """

    playwright = None
    browser = None

    url = STATE.get("url")  # SAFE ACCESS

    if not url or not isinstance(url, str) or url.strip() == "":
        print("❌ INVALID URL in STATE['url']")
        return None

    try:
        playwright = await async_playwright().start()

        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"🌐 Opening: {url}")

        await page.goto(url, timeout=60000)

        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3000)

        print("🚀 SYSTEM STARTED...")

        text = await page.inner_text("body")
        lines = text.splitlines()

        status = detect_game_status(lines)

        print(f"📊 Current Status: {status}")
        # ========== INTELLIGENT STATUS HANDLING ==========
        
        # 1. Match Abandoned - Exit immediately
        if "Abandoned" in status:
            print("❌ Match has been ABANDONED. Exiting...")
            
        # 2. Suspended/Deferred - Exit with message
        if "Suspended" in status or "Deferred" in status:
            print(f"⏸️ Match is {status}. Exiting...")
            
        # 3. Completed - Show result and exit
        if "Completed" in status:
            result_text = status.replace("Completed - ", "")
            #match_title = "KKR vs LSG, 15th T20, IPL 2026 summary"
            print(f"🏆 MATCH FINISHED! {result_text}")
            print("✅ Exiting...")
            
        # 4. Tomorrow - Exit with scheduling info
        if "Tomorrow" in status:
            print(f"📅 Match is scheduled for {status}. Script will exit. Run again tomorrow.")
            
        # 5. Today at specific time
        if "Today at" in status:
            time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM))', status)
            if time_match:
                match_time_str = time_match.group(1)
                now = datetime.now()
                match_time = datetime.strptime(match_time_str, "%I:%M %p")
                match_time = now.replace(hour=match_time.hour, minute=match_time.minute, second=0, microsecond=0)
                
                if now > match_time:
                    print(f"⏰ Match scheduled at {match_time_str} should have started. Checking again...")
                    page.reload()
                    page.wait_for_timeout(2000)
                    text = page.inner_text("body")
                    lines = text.splitlines()
                    status = detect_game_status(lines)
                    print(f"📊 Updated Status: {status}")
                    
                    if "Live" in status:
                        print("🎯 Match is LIVE! Starting main loop...")
                    elif "Completed" in status:
                        result_text = status.replace("Completed - ", "")
                        print(f"🏆 Match already finished! {result_text}")
                    else:
                        print(f"ℹ️ Match status is '{status}'. Exiting.")
                else:
                    wait_seconds = (match_time - now).total_seconds()
                    if wait_seconds > 3600:
                        print(f"📅 Match starts at {match_time_str}. Script will exit. Run closer to match time.")
                    else:
                        print(f"⏳ Match starts at {match_time_str}. Waiting {wait_seconds/60:.1f} minutes...")
                        time.sleep(wait_seconds)
                        page.reload()
                        page.wait_for_timeout(2000)
                        text = page.inner_text("body")
                        lines = text.splitlines()
                        status = detect_game_status(lines)
                        print(f"📊 Updated Status: {status}")
        
        # 6. "Today" without time or "Scheduled" - Exit
        if "Today" in status and "at" not in status:
            print("📅 Match is scheduled for today but no specific time found. Exiting. Run manually when match starts.")
            
        if "Scheduled" in status:
            print("📅 Match is scheduled but not started yet. Exiting. Run closer to match time.")
            
        # 7. "Yet to Start" - Wait for toss/live
        if "Yet to Start" in status:
            print("🟡 Match yet to start. Waiting for toss/live signal...")
            max_wait_time = 7200
            start_wait = time.time()
            
            while True:
                time.sleep(30)
                page.reload()
                page.wait_for_timeout(2000)
                text = page.inner_text("body")
                lines = text.splitlines()
                new_status = detect_game_status(lines)
                print(f"🔄 Re-check: {new_status}")
                
                if "Live" in new_status:
                    status = new_status
                    print("🎯 Match is now LIVE! Proceeding...")
                    break
                elif "Completed" in new_status:
                    result_text = new_status.replace("Completed - ", "")
                    print(f"🏆 Match already finished! {result_text}")
                   
                elif "Abandoned" in new_status or "Suspended" in new_status:
                    print(f"❌ Match {new_status}. Exiting.")
                   
                elif time.time() - start_wait > max_wait_time:
                    print("⏰ Max wait time exceeded. Match didn't start. Exiting.")
                   
        
        # 8. LIVE MATCH - Main continuous loop with break handling
        if "Live" in status or "Break" in status:
            print("🎬 MATCH IS LIVE! Starting continuous monitoring...")
            print("   Will detect and handle Drinks/Innings breaks automatically")
            print("   Will detect when match finishes with result")
            print("Press Ctrl+C to stop\n")
            #game_welcome(page)
            #refresh_interval = 15
            #last_data_hash = None
            await scraper()
                        
            

        # 9. Unknown status
        if "Unknown" in status:
            print("⚠️ Could not determine match status. Exiting.")
            
            
        
        return status

    except Exception as e:
        print(f"❌ ERROR in run_ai_engine: {e}")
        return None

    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()

#if init_obs():
#        switch_scene("LIVE")
        #switch_scene("REPLAY")
        # switch_scene("CROWD")
        # switch_scene("DRONE")"""    
async def engine_loop():
    """
    Safe continuous engine for FastAPI
    """

    global STOP_ENGINE

    while not STOP_ENGINE:
        await run_ai_engine()
        await asyncio.sleep(5)

    print("🛑 Engine loop stopped safely.")

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


# =========================================================
# STARTUP
# =========================================================


@app.on_event("startup")
async def startup():
    asyncio.create_task(engine_loop())
# =========================================================
# ROUTES
# =========================================================

@app.get("/")
def home():
    return FileResponse("templates/home.html")

@app.get("/overlay")
def overlay():
    return FileResponse("templates/overlay.html")

@app.post("/set-url")
async def set_url(payload: dict):

    STATE["url"] = payload.get("url", "")
    STATE["connected"] = False
    # =========================
    # LOAD FLAGS ONLY ONCE
    # =========================
    await ensure_flags_loaded()
    if STATE["url"]:        
        data = await get_playing_xi(STATE["url"])
    return {"ok": True}



templates = Jinja2Templates(directory="templates")


@app.get("/api/match-status")
async def get_match_status():
    data = await run_ai_engine()
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
    """Serve the playing XI HTML page with team data"""
    
    team_a_html = ""
    team_b_html = ""
    has_data = False
    
    if STATE["url"]:
        try:
            data = await get_playing_xi(STATE["url"])
            STATE["current_playing_xi"] = data
            
            team_a_html = generate_team_html(
                data.get("team_a", {}),
                "team-a"
            )
            
            team_b_html = generate_team_html(
                data.get("team_b", {}),
                "team-b"
            )
            
            has_data = True
            
        except Exception as e:
            print(f"Error fetching playing XI: {e}")
            team_a_html = '<div class="team-container"><div class="team-header team-a">Error Loading</div><div class="players-grid">Failed to load team data</div></div>'
            team_b_html = '<div class="team-container"><div class="team-header team-b">Error Loading</div><div class="players-grid">Failed to load team data</div></div>'
    
    # Read the HTML template
    html_file_path = Path("templates/players.html")
    
    if not html_file_path.exists():
        return HTMLResponse(content="<h1>players.html file not found!</h1>", status_code=404)
    
    with open(html_file_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Replace placeholders with actual data
    if has_data:
        html_content = html_content.replace("{{ TEAM_A_HTML }}", team_a_html)
        html_content = html_content.replace("{{ TEAM_B_HTML }}", team_b_html)
        html_content = html_content.replace("{{ DATA_AVAILABLE }}", "true")
    else:
        html_content = html_content.replace("{{ TEAM_A_HTML }}", '<div class="team-container"><div class="team-header team-a">No Data</div><div class="players-grid">Waiting for data...</div></div>')
        html_content = html_content.replace("{{ TEAM_B_HTML }}", '<div class="team-container"><div class="team-header team-b">No Data</div><div class="players-grid">Waiting for data...</div></div>')
        html_content = html_content.replace("{{ DATA_AVAILABLE }}", "false")
    
    return HTMLResponse(content=html_content)

@app.get("/api/playing-xi")
async def get_playing_xi_api():
    """API endpoint to get playing XI data as JSON"""
    # Initialize STATE["current_playing_xi"] if it doesn't exist
    if "current_playing_xi" not in STATE:
        STATE["current_playing_xi"] = None
    
    if STATE.get("url"):
        try:
            data = await get_playing_xi(STATE["url"])
            STATE["current_playing_xi"] = data
            return {
                "success": True,
                "team_a": data.get("team_a", {}),
                "team_b": data.get("team_b", {})
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": str(e), "team_a": {}, "team_b": {}}
            )
    
    # Safe check using .get() to avoid KeyError
    if STATE.get("current_playing_xi"):
        return {
            "success": True,
            "team_a": STATE["current_playing_xi"].get("team_a", {}),
            "team_b": STATE["current_playing_xi"].get("team_b", {})
        }
    
    return {"success": False, "team_a": {}, "team_b": {}}


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