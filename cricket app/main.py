from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import asyncio
import random
from player_list import get_playing_xi, generate_team_html
from commentry import generate_wicket_commentary, generate_winning_commentary, generate_event_commentary,generate_toss_commentary, demonstrate_toss_scenarios, pre_game_scenario_commentary, generate_break_commentary, generate_full_commentary
from game_status import detect_game_status, handle_break_period
from commentry_dic import WELCOME_COMMENTARY_TEMPLATES
from commentry_dic import COMMENTARY
from utill import number_to_bangla_words
import re
from pydantic import BaseModel
from voice import speak_bangla 
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
    "connected": False,
    "flags": {
        "team_a_flag": "",
        "team_a_name":"",
        "team_a_full_name": "TEAM A",        
        "team_b_flag": "",
        "team_b_name":"",
        "team_b_full_name": "TEAM B",
        "match_info": ""
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
    "Rain Break (Delayed)": "RAIN_DELAY"
}
# =====================================================
# 🎯 EVENT DETECTION (FAST)
# =====================================================

# =========================
# COMMENTARY GENERATOR
# =========================
RUN_COMMENTARY = {
    "0": "ডট বল! কোনো রান হয়নি।",
    "1": "এক রান নেওয়া হলো।",
    "2": "দারুণ দৌড়ে দুই রান!",
    "3": "খুব ভালো রানিং, তিন রান!",
    "4": "চার রান! দারুণ শট, বাউন্ডারি!",
    "6": "ছক্কা! বলটা স্টেডিয়ামের বাইরে!",
}
EXTRA_COMMENTARY = {
    "Wide": "ওয়াইড বল! অতিরিক্ত রান পেল ব্যাটিং দল।",
    "No Ball": "নো বল! ফ্রি হিটের সুযোগ আসতে পারে।",
    "Bye": "বাই রান! ব্যাটে না লেগেই রান এসেছে।",
}
WICKET_COMMENTARY = {
    "Wicket": "উইকেট! ব্যাটসম্যান আউট! দর্শকরা উল্লাসে ফেটে পড়ছে!",
}
BREAK_COMMENTARY = {
    "Innings Break": "ইনিংস বিরতি! এখন দ্বিতীয় ইনিংসের প্রস্তুতি চলছে।",
    "Drinks Break": "পানীয় বিরতি চলছে, খেলোয়াড়রা বিশ্রামে।",
    "Tea Break": "টি ব্রেক চলছে, খেলায় সাময়িক বিরতি।",
    "Lunch Break": "লাঞ্চ বিরতি! প্রথম সেশন শেষ।",
    "Rain Break": "বৃষ্টির কারণে খেলা বন্ধ আছে।",
    "Rain Break (Delayed)": "বৃষ্টির কারণে খেলা দেরিতে শুরু হবে।",
}
def get_bangla_commentary(event):
    return (
        RUN_COMMENTARY.get(event)
        or EXTRA_COMMENTARY.get(event)
        or WICKET_COMMENTARY.get(event)
        or BREAK_COMMENTARY.get(event)
        or "যারা নতুন যুক্ত হয়েছেন, স্বাগতম!"
    )
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

def generate_continuous_commentary(events, batsmen, bowler, score, over, team1=None, team2=None, context=None):
    """
    Generate a smooth, human-like cricket commentary for a sequence of events
    - events: list of strings (SIX, FOUR, WICKET, DOUBLE, SINGLE, DOT, WIDE, NO_BALL, OVER_COMPLETE)
    - batsmen: list of dicts [{'name':str,'runs':int}, ...]
    - runs: total runs
    - wickets: total wickets
    - over: current over (float)
    - team1, team2: optional team names for updates
    """
    """has_alpha = any(c.isalpha() for c in context)
    #has_digit = any(c.isdigit() for c in context)
    
    status = None
    if has_alpha:
        status = context
        print("Context", context)"""
    
    runs, wickets = map(int, score.split("/"))
    #print(runs, wickets)   
    
    parts = []
    
    if events == "BOWLER_RUNUP":
        bowler_name = bowler.get("name", "বোলার")
        comment = random.choice(COMMENTARY["BOWLER_RUNUP"]).format(bowler=bowler_name)
        parts.append(comment)                      

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
async def scrap_page(page):
    return await page.evaluate("""
            () => {

                // =================================================
                // HELPERS
                // =================================================

                const clean = (t) =>
                    (t || "")
                        .replace(/\\s+/g, " ")
                        .trim();

                const safeText = (selector) => {

                    const el = document.querySelector(selector);

                    return el
                        ? clean(el.innerText)
                        : "";
                };

                const safeImg = (selector) => {

                    const el = document.querySelector(selector);

                    return el
                        ? el.src
                        : "";
                };

                // =================================================
                // DATA OBJECT
                // =================================================

                const data = {

                    // MATCH
                    team_a: "",
                    team_b: "",

                    score: "",
                    overs: "",
                    crr: "",

                    status: "",
                    commentary: "",
                    batting:"",                            

                    // BOWLER
                    bowler: "",
                    bowler_fig: "",
                    bowler_img: "",

                    // STRIKER
                    striker: "",
                    striker_runs: "",
                    striker_balls: "",
                    striker_full: "",
                    striker_img: "",

                    // NON STRIKER
                    non_striker: "",
                    non_striker_runs: "",
                    non_striker_balls: "",
                    non_striker_full: "",
                    non_striker_img: "",

                    // EXTRA
                    partnership: "",
                    last_wicket: "",

                    // TIMELINE
                    overs_timeline: [],

                    // RESULT
                    result_boxes: [],
                                         
                    //Target Run
                    target: "",

                    // PLAYERS
                    live_players: {
                        batsmen: [],
                        bowler: null
                    },

                    updated: Date.now()
                };

                // =================================================
                // BODY TEXT
                // =================================================

                const bodyText =
                    clean(document.body.innerText);

                // =================================================
                // TEAM NAMES
                // =================================================

                /*const teamMatch =
                    bodyText.match(
                        /([A-Za-z\\s\\-]+)\\s+vs\\s+([A-Za-z\\s\\-]+)/i
                    );

                if (teamMatch) {

                    data.team_a =
                        clean(teamMatch[1]);

                    data.team_b =
                        clean(teamMatch[2]);
                }*/

                // =================================================
                // SCORE + OVERS
                // Example:
                // 147-2 (14.2)
                // 147/2 14.2
                // =================================================

                const scoreOverMatch = bodyText.match(
                    /(\d{1,3})\s*[-/]\s*(\d{1})\s*(\d+)\.(\d)/
                );

                if (scoreOverMatch) {

                    const runs = parseInt(scoreOverMatch[1]);      // 86
                    const wickets = parseInt(scoreOverMatch[2]);   // 1
                    const over = parseInt(scoreOverMatch[3]);      // 8
                    const ball = parseInt(scoreOverMatch[4]);      // 5

                    data.score = `${runs}/${wickets}`;

                    // keep CREX-style overs format
                    data.overs = `${over}.${ball}`;

                    // optional: total balls (VERY IMPORTANT for logic)
                    data.balls = (over * 6) + ball;
                }
                // =================================================
                // CRR
                // =================================================

                const crrMatch =
                    bodyText.match(
                        /CRR\\s*:?\\s*(\\d+\\.\\d+)/i
                    );

                if (crrMatch) {

                    data.crr =
                        crrMatch[1];
                }

                // =================================================
                // STATUS
                // =================================================

                const statusMatch =
                    bodyText.match(
                        /(LIVE|Match Info|Stumps|Innings Break|Opt to Bat|Won by.*)/i
                    );

                if (statusMatch) {

                    data.status =
                        clean(statusMatch[1]);
                }

                // =================================================
                // COMMENTARY
                // =================================================

               /* const commentaryEl =
                    document.querySelector(
                        ".commentary-text, .live-commentary, .commentary"
                    );

                if (commentaryEl) {

                    data.commentary =
                        clean(commentaryEl.innerText);
                }*/

                const teamBlocks =
                    document.querySelectorAll(
                    ".team-content"
                    );

                    // TEAM A
                    if (teamBlocks.length >= 1) {

                    const team1 = teamBlocks[0];

                    const team1Name =
                        team1.querySelector(".team-name");
                    

                    if (team1Name) {

                        data.batting =
                            clean(team1Name.innerText);
                    }                    

                    }
                    
                // =================================================
                // PARTNERSHIP
                // =================================================

                const partnershipMatch =
                    bodyText.match(
                        /(\\d+)\\((\\d+)\\)/
                    );

                if (partnershipMatch) {

                    data.partnership =
                        `${partnershipMatch[1]}(${partnershipMatch[2]})`;
                }

                // =================================================
                // LAST WICKET
                // =================================================

                const wicketMatch =
                    bodyText.match(
                        /Last Wkt\\s*:??\\s*(.*)/i
                    );

                if (wicketMatch) {

                    data.last_wicket =
                        clean(wicketMatch[1]);
                }

                // =================================================
                // RESULT BOXES
                // =================================================

                document
                    .querySelectorAll(".result-box")
                    .forEach(el => {

                        const txt =
                            clean(el.innerText);

                        if (txt) {

                            data.result_boxes.push(txt);
                        }
                    });

                // =================================================
                // LIVE PLAYER SECTION
                // =================================================

                const playerSection =
                    document.querySelector(
                        ".player-profile"
                    );

                if (playerSection) {

                    // =============================================
                    // BATSMEN
                    // =============================================

                    const batsmenCards =
                        playerSection.querySelectorAll(
                            ".batsmen-partnership"
                        );

                    batsmenCards.forEach(card => {

                        // Skip bowler card
                        if (
                            card.querySelector(
                                ".batsmen-score.bowler"
                            )
                        ) {
                            return;
                        }

                        const img =
                            card.querySelector(
                                ".batsmen-image img"
                            );

                        const name =
                            card.querySelector(
                                ".batsmen-name p"
                            );

                        const scorePs =
                            card.querySelectorAll(
                                ".batsmen-score p"
                            );

                        let runs = "";
                        let balls = "";

                        if (scorePs.length >= 2) {

                            runs =
                                clean(scorePs[0].innerText);

                            balls =
                                clean(scorePs[1].innerText)
                                    .replace(/[()]/g, "");
                        }

                        data.live_players.batsmen.push({

                            name: name
                                ? clean(name.innerText)
                                : "",

                            runs: runs,

                            balls: balls,

                            image: img
                                ? img.src
                                : ""
                        });
                    });

                    // =============================================
                    // BOWLER
                    // =============================================

                    const bowlerCard =
                        playerSection.querySelector(
                            ".batsmen-partnership:has(.batsmen-score.bowler)"
                        );

                    if (bowlerCard) {

                        const bowlerImg =
                            bowlerCard.querySelector(
                                ".batsmen-image img"
                            );

                        const bowlerName =
                            bowlerCard.querySelector(
                                ".batsmen-name p"
                            );

                        const figures =
                            bowlerCard.querySelectorAll(
                                ".batsmen-score.bowler p"
                            );

                        let fig = "";

                        if (figures.length >= 2) {

                            fig =
                                clean(figures[0].innerText) +
                                " " +
                                clean(figures[1].innerText);
                        }

                        data.live_players.bowler = {

                            name: bowlerName
                                ? clean(bowlerName.innerText)
                                : "",

                            figures: fig,

                            image: bowlerImg
                                ? bowlerImg.src
                                : ""
                        };
                    }
                }

                // =================================================
                // STRIKER
                // =================================================

                if (
                    data.live_players.batsmen.length >= 1
                ) {

                    const s =
                        data.live_players.batsmen[0];

                    data.striker =
                        s.name;

                    data.striker_runs =
                        s.runs;

                    data.striker_balls =
                        s.balls;

                    data.striker_full =
                        `${s.name} ${s.runs} (${s.balls})`;

                    data.striker_img =
                        s.image;
                }

                // =================================================
                // NON STRIKER
                // =================================================

                if (
                    data.live_players.batsmen.length >= 2
                ) {

                    const ns =
                        data.live_players.batsmen[1];

                    data.non_striker =
                        ns.name;

                    data.non_striker_runs =
                        ns.runs;

                    data.non_striker_balls =
                        ns.balls;

                    data.non_striker_full =
                        `${ns.name} ${ns.runs} (${ns.balls})`;

                    data.non_striker_img =
                        ns.image;
                }

                // =================================================
                // BOWLER
                // =================================================

                if (data.live_players.bowler) {

                    data.bowler =
                        data.live_players.bowler.name;

                    data.bowler_fig =
                        data.live_players.bowler.figures;

                    data.bowler_img =
                        data.live_players.bowler.image;
                }

                // =================================================
                // OVERS TIMELINE
                // =================================================

                document
                    .querySelectorAll(".overs-slide")
                    .forEach(overEl => {

                        const overData = {

                            over: "",
                            balls: [],
                            total: ""
                        };

                        // OVER TITLE

                        const overTitle =
                            overEl.querySelector("span");

                        if (overTitle) {

                            overData.over =
                                clean(overTitle.innerText);
                        }

                        // BALLS

                        overEl
                            .querySelectorAll(".over-ball")
                            .forEach(ball => {

                                const val =
                                    clean(ball.innerText);

                                if (val) {

                                    overData.balls.push(val);
                                }
                            });

                        // TOTAL

                        const total =
                            overEl.querySelector(".total");

                        if (total) {

                            overData.total =
                                clean(
                                    total.innerText.replace("=", "")
                                );
                        }

                        data.overs_timeline.push(overData);
                    });

                                         

                    // =================================================
                    // RESULT / MATCH STATUS
                    // =================================================

                    // final result text
                    const finalResultEl =
                        document.querySelector(
                            ".final-result.m-none"
                        );

                    if (finalResultEl) {

                        const resultText =
                            clean(finalResultEl.innerText);

                        if (resultText) {

                            // main status
                            //data.status = resultText;

                            // separate field
                            data.target = resultText;

                            // push to result boxes
                            //data.result_boxes.push(resultText);
                        }
                    }
                // =================================================
                // RETURN
                // =================================================

                return data;
            }
            """)

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
                
                if event != last_event:
                    
                    commentary = generate_continuous_commentary(detect_event(event), batsman, bowler, parsed["score"], full_over, STATE["flags"].get("team_a_full_name"), STATE["flags"].get("team_b_full_name"), event)
                    #commentary = get_bangla_commentary(event)  
                    
                    if commentary:
                        print("Testset")
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
        #print(cards)
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
                matches.append({
                    "text": text,
                    "url": href
                })

            except Exception as e:
                print("❌ CARD ERROR:", e)
                continue

        await browser.close()

    return matches


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
    asyncio.create_task(scraper())

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

    return {"ok": True}


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
        await ensure_flags_loaded()    
       

        while True:
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        clients.remove(websocket)
        print("❌ CLIENT DISCONNECTED")


# =========================================================
# HTML PAGE
# =========================================================

@app.get("/players", response_class=HTMLResponse)
async def home():
    if STATE["url"]:
        data = await get_playing_xi(STATE["url"])

        team_a_html = generate_team_html(
            data["team_a"],
            "team-a"
        )

        team_b_html = generate_team_html(
            data["team_b"],
            "team-b"
        )

        html = f"""
        <!DOCTYPE html>
        <html lang="en">

        <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>Playing XI</title>

        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">

        <style>

        *{{
            margin:0;
            padding:0;
            box-sizing:border-box;
        }}

        body{{
            background:#050505;
            color:#fff;
            font-family:'Poppins',sans-serif;
            padding:30px;
        }}

        .main-title{{
            text-align:center;
            font-size:60px;
            font-weight:900;
            margin-bottom:40px;

            background:linear-gradient(
                90deg,
                #fff,
                #ffd84d,
                #ff9800
            );

            -webkit-background-clip:text;
            -webkit-text-fill-color:transparent;
        }}

        .teams{{
            display:grid;
            grid-template-columns:1fr 1fr;
            gap:30px;
        }}

        .team-container{{
            background:
            linear-gradient(
                135deg,
                rgba(255,255,255,.08),
                rgba(255,255,255,.03)
            );

            border:1px solid rgba(255,255,255,.08);

            border-radius:30px;

            overflow:hidden;
        }}

        .team-header{{
            padding:22px;
            font-size:32px;
            font-weight:900;
            text-align:center;
        }}

        .team-a{{
            background:
            linear-gradient(
                135deg,
                #ff003c,
                #ff9800
            );
        }}

        .team-b{{
            background:
            linear-gradient(
                135deg,
                #6a00ff,
                #c400ff
            );
        }}

        .players-grid{{
            padding:20px;

            display:grid;
            grid-template-columns:1fr 1fr;
            gap:18px;
        }}

        .player-card{{
            display:flex;
            align-items:center;
            gap:15px;

            padding:16px;

            border-radius:20px;

            background:
            linear-gradient(
                135deg,
                rgba(255,255,255,.08),
                rgba(255,255,255,.02)
            );

            transition:.3s;
        }}

        .player-card:hover{{
            transform:translateY(-5px);
        }}

        .player-img{{
            width:80px;
            height:80px;

            border-radius:50%;
            object-fit:cover;

            border:3px solid rgba(255,255,255,.15);
        }}

        .player-info{{
            flex:1;
        }}

        .player-name{{
            font-size:20px;
            font-weight:800;
            line-height:1.3;
        }}

        .tag{{
            color:#ffd84d;
            margin-left:6px;
        }}

        .player-role{{
            margin-top:8px;

            display:inline-block;

            padding:5px 12px;

            border-radius:30px;

            background:rgba(0,229,255,.12);

            border:1px solid rgba(0,229,255,.25);

            color:#00e5ff;

            font-size:12px;
            font-weight:700;
        }}

        @media(max-width:1200px){{
            .teams{{
                grid-template-columns:1fr;
            }}
        }}

        @media(max-width:700px){{
            .players-grid{{
                grid-template-columns:1fr;
            }}

            .main-title{{
                font-size:38px;
            }}
        }}

        </style>

        </head>

        <body>

            <div class="main-title">
                PLAYING XI
            </div>

            <div class="teams">

                {team_a_html}

                {team_b_html}

            </div>

        </body>

        </html>
        """

    return HTMLResponse(content=html)


# =========================================================
# JSON API
# =========================================================

@app.get("/api/players")
async def api_players():

    data = await get_playing_xi()

    return JSONResponse(content=data)