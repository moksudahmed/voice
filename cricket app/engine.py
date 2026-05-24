from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi import Body
import asyncio
import random
from player_list import get_playing_xi, generate_team_html
from commentry import generate_continuous_commentary
from game_status import detect_game_status, handle_break_period
from commentry_dic import WELCOME_COMMENTARY_TEMPLATES
from commentry_dic import COMMENTARY
from utill import number_to_bangla_words
import re
from pydantic import BaseModel
from voice import speak_bangla, stop_current_tts, reset_stop_flag
from scraper import scrap_page
# =========================================================
# STATE
# =========================================================

STATE = {
    "url": "",
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
    "Time Out": "TIME_OUT",
    "Strategic Timeout": "STRATEGIC_TIMEOUT"

}

# =========================
# GLOBALS
# =========================
FLAGS_LOADED = False
FLAGS_URL = None
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
# SCENE LOGIC
# =========================
def scene_logic(text):
    t = text.upper()

    if "WICKET" in t:
        return "REPLAY"
    if "SIX" in t or " 6 " in t:
        return "CROWD"

    return "LIVE"

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

# =========================================================
# CLEANER
# =========================================================

def clean(t):
    return re.sub(r"\s+", " ", t).strip() if t else ""

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

async def scraper():

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()
    innings_state = False
    last_state = None
    last_event = ""
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
           
            if parsed != last_state:
                last_state = parsed
                STATE["data"] = parsed
                event = parsed["result_boxes"][0]
                
                print(event)
                
                #STATE["data"]["commentary"]= event
                #batsmen = parsed["result_boxes"][0]
                
                batsman = parse_batsmen(parsed)
                
                bowler = parse_bowler(parsed["live_players"]['bowler'])                          
                
                full_over = int(parsed["overs"].split(".")[0])
                #STATE["data"]["result_boxes"] = "4"
                if event != last_event:
                    

                    teamA = STATE["flags"].get("team_a_bangla_name") or STATE["flags"].get("team_a_full_name") or STATE["flags"].get("team_a_name") or "TEAM A"
                    teamB = STATE["flags"].get("team_b_bangla_name") or STATE["flags"].get("team_b_full_name") or STATE["flags"].get("team_b_name") or "TEAM B"
                    
                    commentary = generate_continuous_commentary(detect_event(event), batsman, bowler, parsed["score"], 
                                                                    full_over, teamA, 
                                                                    teamB, event)
                    #commentary = get_bangla_commentary(event)  
                    
                    if commentary:
                        
                        STATE["data"]["commentary"] = commentary
                        
                        speak_bangla(commentary) 
                        print(commentary)
                    last_event = event
                dead = []

                if event == "Innings Break" and not innings_state and is_valid_flags(STATE.get("flags")):                
                    #print("Check innings break")
                    swap_teams(STATE["flags"])
                    #print("State Changed:", STATE["flags"])
                    innings_state = True
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
            
           
            
            await asyncio.sleep(0.12)

        except Exception as e:
            print("❌ SCRAPER ERROR:", e)
            STATE["connected"] = False
            await asyncio.sleep(2)


