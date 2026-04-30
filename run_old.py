from playwright.sync_api import sync_playwright
import re
import json
import time
import random
import asyncio
import edge_tts
import os
import time
import sys
import re
from datetime import datetime
import threading
from queue import Queue
from commentry import generate_wicket_commentary, generate_winning_commentary, generate_event_commentary,generate_toss_commentary, demonstrate_toss_scenarios, pre_game_scenario_commentary, generate_break_commentary, generate_full_commentary
from voice import speak
from game_status import detect_game_status, handle_break_period
from commentry_dic import WELCOME_COMMENTARY_TEMPLATES
from commentry_dic import COMMENTARY
from utill import number_to_bangla_words
# ---------------------------------------
# CONFIG
# ---------------------------------------
#CREX_URL = "https://crex.com/cricket-live-score/mi-vs-srh-41st-match-indian-premier-league-2026-match-updates-118M"
OUTPUT_FILE = "C:/cricket_voices/score.json"
TEAM1 = "মুম্বাই ইন্ডিয়ান্স" 
TEAM2 = "সানরাইজার্স হায়দরাবাদ"
match_title = "MI vs SRH, 41st T20, IPL 2026 live"
REFRESH_INTERVAL = 1  # seconds


# ---------------------------------------
# STATE
# ---------------------------------------
last_runs = None
last_wickets = None
last_over = None
last_ball = None
welcome_played = False
welcome_msg = """
"""
 
def parse_winning_info(text):
    """
    Extract winning result from raw text
    Example:
    'RCB won by 6 wickets'
    'India won by 25 runs'
    """

    text = text.lower()

    result = {
        "team": None,
        "type": None,   # "wickets" or "runs"
        "margin": None
    }

    # Pattern: Team won by X wickets/runs
    match = re.search(r'([a-z\s]+?) won by (\d+) (wickets|runs)', text)

    if match:
        result["team"] = match.group(1).strip().title()
        result["margin"] = int(match.group(2))
        result["type"] = match.group(3)

    return result


def generate_continuous_commentary2(events, batsmen, runs, wickets, over):
    parts = []

    # Priority events
    if "WICKET" in events:        
        line = generate_wicket_commentary(runs, wickets, over, batsmen)
        parts.append(line)

    if "SIX" in events:
        line = generate_event_commentary(events)    
        parts.append(line)

    elif "FOUR" in events:
        parts.append(random.choice(COMMENTARY["FOUR"]))

    elif "DOUBLE" in events:
        parts.append(random.choice(COMMENTARY["DOUBLE"]))

    elif "SINGLE" in events:
        parts.append(random.choice(COMMENTARY["SINGLE"]))

    elif "DOT" in events:
        parts.append(random.choice(COMMENTARY["DOT"]))

    if "WIDE" in events:
        parts.append(random.choice(COMMENTARY["WIDE"]))

    if "NO_BALL" in events:
        parts.append(random.choice(COMMENTARY["NO_BALL"]))

    # ---------------------------------------
    # BATSMAN STATUS
    # ---------------------------------------
    if batsmen and len(batsmen) >= 2:
        b1 = batsmen[0]
        b2 = batsmen[1]

        parts.append(
            f"{b1['name']} খেলছেন {b1['runs']} রান, {b2['name']} করছেন {b2['runs']} রান।"
        )

    # ---------------------------------------
    # OVER COMPLETE
    # ---------------------------------------
    if "OVER_COMPLETE" in events:
        parts.append(
            f"ওভার শেষ। স্কোর এখন {runs}-{wickets}, {over} ওভার শেষে।"
        )

    return " ".join(parts)

def generate_welcome_message(team1, team2):
    template = random.choice(WELCOME_COMMENTARY_TEMPLATES)
    return template.format(team1=team1, team2=team2)
    
def number_to_bangla_words(n):
    """Convert number to Bangla words for TTS-friendly commentary"""
    # Simple example, can be extended
    bn_digits = {
        0: "শূন্য", 1: "এক", 2: "দুই", 3: "তিন", 4: "চার",
        5: "পাঁচ", 6: "ছয়", 7: "সাত", 8: "আট", 9: "নয়", 10: "দশ"
    }
    if n in bn_digits:
        return bn_digits[n]
    return str(n)  # fallback
    
def get_milestone_comment(name, runs):
    """Return milestone commentary for 50/100 runs."""
    if runs == 50:
        return f"🎉 কী দুর্দান্ত ব্যাটিং! {name} এখন হাফ সেঞ্চুরি (৫০ রান) পূর্ণ করেছে!"
    elif runs == 100:
        return f"🔥 অসাধারণ ইনিংস! {name} সেঞ্চুরি (১০০ রান) পূর্ণ করেছে! গ্যালারি উল্লাসে ফেটে পড়ছে!"
    return None

def generate_continuous_commentary(events, batsmen, runs, wickets, over, team1=None, team2=None, context=None):
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
    
def generate_continuous_commentary_eng(events, batsmen, runs, wickets, over, team1=None, team2=None, context=None):
    """
    Generate a smooth, human-like cricket commentary for a sequence of events
    - events: list of strings (SIX, FOUR, WICKET, DOUBLE, SINGLE, DOT, WIDE, NO_BALL, OVER_COMPLETE)
    - batsmen: list of dicts [{'name':str,'runs':int}, ...]
    - runs: total runs
    - wickets: total wickets
    - over: current over (float)
    - team1, team2: optional team names for updates
    """

    parts = []

    # 1️⃣ WICKET has highest priority
    if "WICKET" in events:
        parts.append(generate_wicket_commentary(runs, wickets, over, batsmen[0]['name'] if batsmen else None))

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
        parts.append(
            f"{b1['name']} is on {b1['runs']} runs, {b2['name']} is on {b2['runs']} runs."
        )
    elif batsmen and len(batsmen) == 1:
        b1 = batsmen[0]
        parts.append(f"{b1['name']} is on {b1['runs']} runs.")

    # 5️⃣ Over complete summary
    if "OVER_COMPLETE" in events:
        over_comment = f"End of over {over}. The score is {runs} runs for {wickets} wickets."
        parts.append(over_comment)

        # 6️⃣ Welcome message and quick update for new viewers
        if team1 and team2:
            welcome_msg = (
                f"Welcome to everyone who just joined! "
                f"In this {team1} vs {team2} match, the score is {runs} runs for {wickets} wickets. "
                f"{over} overs have been completed, the team is progressing well. The excitement continues!"
            )
            parts.append(welcome_msg)

    # Combine all commentary parts naturally
    return " ".join(parts)
# ---------------------------------------
# PARSE SCORE (ROBUST)
# ---------------------------------------

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
# ---------------------------------------
# GET SCORE TEXT
# ---------------------------------------
def get_score_text(page):
    """
    Try multiple selectors to get full score (runs-wickets + overs)
    """
    selectors = [
        "div[class*='innings'] span[class*='score']",  # main score element
        "div[class*='score']",                         # fallback
    ]
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                text = el.inner_text().strip()
                if text:
                    return text
        except:
            continue
    # final fallback
    try:
        return page.inner_text("body")
    except:
        return ""

# ---------------------------------------
# GET COMMENTARY
# ---------------------------------------
def get_commentary(page):
    try:
        el = page.query_selector("div[class*='commentary']")
        if el:
            return el.inner_text().lower()
    except:
        pass
    return ""

# ---------------------------------------
# DETECT EVENT
# ---------------------------------------

  
def detect_run(run_diff):
    """
    Return run-based event
    """
    if run_diff == 0:
        return "DOT"
    elif run_diff == 1:
        return "SINGLE"
    elif run_diff == 2:
        return "DOUBLE"
    elif run_diff == 3:
        return "TRIPLE"
    elif run_diff == 4:
        return "FOUR"
    elif run_diff >= 6:
        return "SIX"
    return None

def detect_wicket_advanced(text):
    if not text:
        return None

    t = text.lower()

    if "caught out" in t or "c " in t:
        return "CAUGHT"
    if "lbw" in t:
        return "LBW"
    if "bowled" in t or "b " in t:
        return "BOWLED"
    if "stumped" in t or "st " in t:
        return "STUMPED"
    if "run out" in t:
        return "RUN_OUT"
    if "hit wicket" in t:
        return "HIT_WICKET"
    if "timed out" in t:
        return "TIMED_OUT"
    if "\nw\n" in t or " out" in t:
        return "WICKET"

    return None
    
    
def detect_event(runs, wickets, over, ball, commentary_text=""):
    global last_runs, last_wickets, last_over, last_ball

    if last_runs is None:
        last_runs, last_wickets, last_over, last_ball = runs, wickets, over, ball
        return []

    events = []
    text = commentary_text.lower()

    run_diff = runs - last_runs
    wicket_diff = wickets - last_wickets

    same_ball = (over == last_over and ball == last_ball)
    new_ball = not same_ball
    over_changed = (last_over is not None and over > last_over)

    # -----------------------------
    # TEXT FLAGS
    # -----------------------------
    is_wide = "wide" in text
    is_no_ball = "no ball" in text or "no-ball" in text
    # -----------------------------
    # 🔵 OVER COMPLETE
    # -----------------------------
    if over_changed:
        events.append("OVER_COMPLETE")
        
    # -----------------------------
    # 🟥 WICKET
    # -----------------------------
    if wicket_diff > 0:
        events.append("WICKET")
    
    else:
        # -----------------------------
        # 🟡 EXTRAS (FIXED LOGIC)
        # -----------------------------
        if same_ball and run_diff > 0:

            extra_type = None

            # Priority 1: Text detection
            if is_no_ball:
                extra_type = "NO_BALL"
            elif is_wide:
                extra_type = "WIDE"

            # Priority 2: Smart fallback (🔥 NEW)
            elif run_diff >= 2:
                # Assume at least 1 extra happened
                extra_type = "WIDE"

            if extra_type:
                events.append(extra_type)
                extra_runs = run_diff - 1
            else:
                extra_runs = run_diff

            # Bat runs after extra
            if extra_runs > 0:
                run_event = detect_run(extra_runs)
                if run_event:
                    events.append(run_event)

        # -----------------------------
        # 🟢 NORMAL BALL
        # -----------------------------
        elif new_ball:
            if run_diff > 0:
                run_event = detect_run(run_diff)
                if run_event:
                    events.append(run_event)
            else:
                events.append("DOT")

    

    # remove duplicates
    events = list(dict.fromkeys(events))

    # update state
    last_runs, last_wickets, last_over, last_ball = runs, wickets, over, ball

    return events
    

    
# ---------------------------------------
# WRITE JSON
# ---------------------------------------
def write_json(runs, wickets, over, ball, event):
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "runs": runs,
                "wickets": wickets,
                "over": over,
                "ball": ball,
                "event": event,
                event: ""
            }, f, indent=4)
    except Exception as e:
        print("JSON Error:", e)


    
def batsman_commentary(batsmen):
    if len(batsmen) == 2:
        b1, b2 = batsmen
        return f"{b1['name']} {b1['runs']} রানে খেলছেন, আর {b2['name']} করেছেন {b2['runs']} রান।"
        
def game_welcome(page):
        welcome_played = False
        last_toss_text = None

    #while True:
        try:
            # ---------------------------------------
            # GET FULL PAGE TEXT
            # ---------------------------------------
            text = page.inner_text("body")
            
            # ---------------------------------------
            # PARSE SCORE
            # ---------------------------------------
            score = parse_score(text)
            print("PARSED:", score)

            runs, wickets, over, ball = score
            print(runs)
            # ---------------------------------------
            # MATCH NOT STARTED
            # ---------------------------------------
            if runs == 0 and over == 0 and ball == 0:

                # First time welcome message
                if not welcome_played:
                    line = generate_welcome_message(
                                TEAM1,
                                TEAM2 
                            )
                    #line = random.choice(COMMENTARY["WELCOME"])
                    speak("WELCOME", line)
                    welcome_played = True
                    time.sleep(2)

                # Get latest status line (toss / delay / players entering)
                lines = text.split("\n")
                current_status = lines[16] if len(lines) > 16 else ""

                # If new update এসেছে (avoid repeat)
                if current_status and current_status != last_toss_text:
                    #commentary = pre_game_scenario_commentary(current_status)
                    
                    # Add natural flow
                    line = generate_welcome_message(
                                TEAM1,
                                TEAM2 
                            )
                    final_line = welcome_msg #commentary + " " + line
                    
                    speak("TOSS", final_line)
                    last_toss_text = current_status
                    time.sleep(2)

                #continue

            # ---------------------------------------
            # MATCH STARTED → EXIT
            # ---------------------------------------
            else:
                speak("INFO", "খেলা শুরু হয়ে গেছে, এখন সরাসরি লাইভ স্কোর আপডেটে চলে যাচ্ছি!")
                #break

        except Exception as e:
            print("Error in game_welcome:", e)
            time.sleep(2)
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
def detect_event(event):
    return RUN_EVENT_MAP.get(event) or EXTRA_EVENT_MAP.get(event)

# ---------------------------------------
# ---------------------------------------
# MAIN LOOP
# ---------------------------------------     

def extract_match_data(lines):
    """
    Extract relevant match data from page lines.
    """
    score_info = []
    
    for i, line in enumerate(lines):
        if isinstance(line, str):
            # Check for score like "189/8" or "127-4"
            if re.search(r'\d{1,3}/\d{1,2}', line) or re.search(r'\d{1,3}-\d{1,2}', line):
                score_info.append(line)
            
            # Check for overs
            if re.search(r'\d{1,2}\.\d{1,2}\s*overs?', line.lower()):
                score_info.append(line)
            
            # Check for run rate
            if "run rate" in line.lower():
                score_info.append(line)
    
    if score_info:
        return ' | '.join(score_info[:3])
    
    return "Match in progress..."


def ai_commentry(CREX_URL):
    global welcome_played
    speak("WELCOME",welcome_msg)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(CREX_URL)
        #page.goto(CREX_URL)
        page.goto(CREX_URL, timeout=60000)
        page.wait_for_load_state("networkidle")  # VERY IMPORTANT
        page.wait_for_timeout(3000)
       # page.wait_for_load_state("domcontentloaded")
       # page.wait_for_timeout(2000)
        print("🚀 SYSTEM STARTED...")
        text = page.inner_text("body")                
                
        lines = text.splitlines()        
        status = detect_game_status(lines)
        
        print(f"📊 Current Status: {status}")
        
        # ========== INTELLIGENT STATUS HANDLING ==========
        
        # 1. Match Abandoned - Exit immediately
        if "Abandoned" in status:
            print("❌ Match has been ABANDONED. Exiting...")
            browser.close()
            sys.exit(0)
        
        # 2. Suspended/Deferred - Exit with message
        if "Suspended" in status or "Deferred" in status:
            print(f"⏸️ Match is {status}. Exiting...")
            browser.close()
            sys.exit(0)
        
        # 3. Completed - Show result and exit
        if "Completed" in status:
            result_text = status.replace("Completed - ", "")
            #match_title = "KKR vs LSG, 15th T20, IPL 2026 summary"
            
            result = generate_full_commentary(result_text, match_title)
            #speak("MATCH_END",result)
            speak("MATCH_END","Hello")
            print("Hi test") 
            print(result)
            print(f"🏆 MATCH FINISHED! {result_text}")
            print("✅ Exiting...")
            #browser.close()
            #sys.exit(0)
        
        # 4. Tomorrow - Exit with scheduling info
        if "Tomorrow" in status:
            print(f"📅 Match is scheduled for {status}. Script will exit. Run again tomorrow.")
            browser.close()
            sys.exit(0)
        
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
                        browser.close()
                        sys.exit(0)
                    else:
                        print(f"ℹ️ Match status is '{status}'. Exiting.")
                        browser.close()
                        sys.exit(0)
                else:
                    wait_seconds = (match_time - now).total_seconds()
                    if wait_seconds > 3600:
                        print(f"📅 Match starts at {match_time_str}. Script will exit. Run closer to match time.")
                        browser.close()
                        sys.exit(0)
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
            browser.close()
            sys.exit(0)
        
        if "Scheduled" in status:
            print("📅 Match is scheduled but not started yet. Exiting. Run closer to match time.")
            browser.close()
            sys.exit(0)
        
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
                    browser.close()
                    sys.exit(0)
                elif "Abandoned" in new_status or "Suspended" in new_status:
                    print(f"❌ Match {new_status}. Exiting.")
                    browser.close()
                    sys.exit(0)
                elif time.time() - start_wait > max_wait_time:
                    print("⏰ Max wait time exceeded. Match didn't start. Exiting.")
                    browser.close()
                    sys.exit(0)
        
        # 8. LIVE MATCH - Main continuous loop with break handling
        if "Live" in status or "Break" in status:
            print("🎬 MATCH IS LIVE! Starting continuous monitoring...")
            print("   Will detect and handle Drinks/Innings breaks automatically")
            print("   Will detect when match finishes with result")
            print("Press Ctrl+C to stop\n")
            game_welcome(page)
            refresh_interval = 15
            last_data_hash = None
            
            try:
                while True:
                    page.reload()
                    page.wait_for_timeout(2000)
                    text = page.inner_text("body")
                    lines = text.splitlines()
                    
                    current_status = detect_game_status(lines)
                    
                    # Check for completed match with result FIRST
                    if "Completed" in current_status:
                        result_text = current_status.replace("Completed - ", "")
                        #commentary = get_winning_commentary(**match_data)
                        print("Hello")
                        result = generate_full_commentary(result_text, match_title)
                        print(result)
                        print(f"\n{'='*60}")
                        print(f"🏆 MATCH FINISHED! {result_text}")
                        print(f"{'='*60}")
                        print("✅ Exiting...")
                        break
                    
                    # Handle breaks
                    elif "Break" in current_status:
                        print(f"\n{'='*50}")
                        print(f"⏸️ BREAK DETECTED: {current_status}")
                        print(f"{'='*50}")
                        score_data = parse_score(text)
                        print("PARSED:", score_data)
                        runs, wickets, over, ball = score_data
                        
                        new_status = handle_break_period(current_status, page, browser, TEAM1, runs, wickets)
                        
                        if new_status == "Live":
                            current_status = new_status
                            print(f"\n🎬 Match resumed! Continuing monitoring...\n")
                            continue
                        elif "Completed" in new_status:
                            result_text = new_status.replace("Completed - ", "")
                            print(f"\n🏆 MATCH FINISHED! {result_text}")
                            break
                        else:                            
                            if new_status ==  "Innings Break":                                
                                print(f"Match status after break: {new_status}")                                                            
                                
                            else:
                                print(f"Match status after break: {new_status}")                            
                            break
                    
                    # Check if match is no longer live
                    elif "Abandoned" in current_status:
                        print("\n❌ MATCH ABANDONED! Exiting...")
                        break
                    elif "Suspended" in current_status:
                        print("\n⏸️ MATCH SUSPENDED! Exiting...")
                        break
                    
                    # Extract match data for live matches
                    if "Live" in current_status:
                        #score_data = extract_match_data(lines)
                        score_data = parse_score(text)
                        print("PARSED:", score_data)
                        runs, wickets, over, ball = score_data
                        
                        # ---------------------------------------
                        # PARSE EACH BALL STATUS
                        # ---------------------------------------
                        last_status_message =""
                        if "CRR" in lines[17]:                                                     
                            last_status_message = lines[16]
                        else : 
                            last_status_message = lines[17]
                        print(last_status_message)
                        
                        has_alpha = any(c.isalpha() for c in last_status_message)
                        #has_digit = any(c.isdigit() for c in context)
                        
                        status = None
                        if has_alpha:
                            status = last_status_message
                            print("Context", status)
                        # ---------------------------------------
                        # PARSE BATSMEN
                        # ---------------------------------------
                        batsmen = parse_batsmen(text)
                        bowler = parse_bowler(text)
                        
                        status = detect_game_status(last_status_message)
                        message = ""
                        if last_status_message and message != last_status_message:
                            
                            if last_status_message == "Ball":  
                                commentary = random.choice(COMMENTARY["BOWLER_RUNUP"]).format(bowler=remove_first_part(clean_name(bowler['bowler'])))                            
                                print(commentary)
                                speak("BOWLER_RUNUP",commentary)
                                
                            elif last_status_message == "Time Out":  
                                commentary = random.choice(COMMENTARY["TIME_OUT"])                            
                                print(commentary)
                                speak("TIME_OUT",commentary)
                            """elif last_status_message == "Caught Out":
                                commentary = random.choice(COMMENTARY["CATCH"])                            
                                print(commentary)
                                speak("CATCH",commentary)
                            elif last_status_message == "Run Out Check":
                                commentary = random.choice(COMMENTARY["RUN_OUT_CHECK"])                            
                                print(commentary)
                                speak("RUN_OUT_CHECK",commentary)"""
                                
                            message = last_status_message   
                           
                            
                            # ---------------------------------------
                            # DETECT EVENTS
                            # ---------------------------------------
                            #events = detect_event(runs, wickets, over, ball, last_status_message) 
                            events = detect_event(last_status_message)
                            if not events:
                                #time.sleep(REFRESH_INTERVAL)
                                continue

                            print("EVENTS:", events)

                            # ---------------------------------------
                            # GENERATE NATURAL COMMENTARY
                            # ---------------------------------------
                            line = generate_continuous_commentary(
                                events,
                                batsmen,
                                runs,
                                wickets,
                                over,
                                TEAM1,
                                TEAM2,
                                last_status_message
                            )
                            event = events
                            print(event)
                            print("🎙 FINAL:", line)
                            # ---------------------------------------
                            # OUTPUT
                            # ---------------------------------------
                            if line:
                                print("🎙 FINAL:", line)

                                # Save last main event
                                write_json(runs, wickets, over, ball, event)
                                print(event)
                                # Speak once (IMPORTANT FIX ✅)
                                speak(event, line)
                            import hashlib
                            data_hash = hashlib.md5(str(score_data).encode()).hexdigest()
                            if data_hash != last_data_hash:
                                prefix = "🏏"
                                print(f"{prefix} [{datetime.now().strftime('%H:%M:%S')}] {score_data}")
                                last_data_hash = data_hash
                        
                    time.sleep(refresh_interval)
                    
            except KeyboardInterrupt:
                print("\n👋 Manual stop requested. Exiting gracefully...")
        
        # 9. Unknown status
        if "Unknown" in status:
            print("⚠️ Could not determine match status. Exiting.")
            browser.close()
            sys.exit(0)
        
        browser.close()

"""if __name__ == "__main__":
    main()"""
    