from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import edge_tts
import asyncio
import threading
import pygame
import io
import asyncio
import time
import re
import threading
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from commentry_dic import COMMENTARY
from commentry import generate_wicket_commentary, generate_winning_commentary, generate_event_commentary,generate_toss_commentary, demonstrate_toss_scenarios, pre_game_scenario_commentary, generate_break_commentary, generate_full_commentary
from commentry_dic import WELCOME_COMMENTARY_TEMPLATES
from utill import number_to_bangla_words
import pyttsx3

TEAM1 = "নিউজিল্যান্ড" 
TEAM2 = "বাংলাদেশ"
# =====================================================
# 🚀 APP
# =====================================================
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def home():
    return FileResponse("static/index.html")


# =====================================================
# 🌐 STATE
# =====================================================
clients = set()

STATE = {
    "voice_enabled": True
}

event_queue = asyncio.Queue()

ACTIVE_MATCH = {
    "url": None,
    "driver": None,
    "running": False
}

def remove_first_part(name):
    parts = name.split(" ", 1)
    return parts[1] if len(parts) > 1 else name

def clean_name(name):
    """
    Remove unwanted text before actual player name
    """
    # Keep only last 2–3 words (typical cricket name)
    words = name.strip().split()
    return " ".join(words[-2:])


# =====================================================
# 🧠 COMMENTARY AI
# =====================================================
def director_ai(text: str):
    t = text.upper()

    if "OUT" in t:
        return "WICKET! HUGE BREAKTHROUGH!"
    if "SIX" in t:
        return "SIX! WHAT A SHOT!"
    if "FOUR" in t:
        return "FOUR RUNS!"
    if "WIDE" in t:
        return "WIDE BALL!"
    if "NO BALL" in t:
        return "NO BALL! FREE HIT!"

    return text


# =====================================================
# 📡 BROADCAST
# =====================================================
async def broadcast(msg):
    dead = set()

    for c in clients:
        try:
            await c.send_text(msg)
        except:
            dead.add(c)

    clients.difference_update(dead)


# =====================================================
# 🔊 TTS (FINAL FIX - OBS WORKING)
# =====================================================
speech_lock = threading.Lock()

def speak2(text: str):
    if not STATE["voice_enabled"]:
        return

    def run():
        with speech_lock:  # prevent overlapping audio
            try:
                print("🎙 SPEAKING:", text)

                engine = pyttsx3.init()   # 🔥 fresh engine each time
                voices = engine.getProperty('voices')
                for voice in voices:
                    if "Bengali" in voice.name or "Bangla" in voice.name:
                        engine.setProperty('voice', voice.id)
                        break
                engine.setProperty("rate", 180)
                engine.setProperty("volume", 1.0)
                
            
                engine.say(text)
                engine.runAndWait()

            except Exception as e:
                print("TTS ERROR:", e)

    threading.Thread(target=run).start()

def speak22(text: str):
    if not STATE["voice_enabled"]:
        return

    def run():
        with speech_lock:
            try:
                print("🎙 SPEAKING:", text)

                engine = pyttsx3.init()

                # ============================
                # 🔍 FIND BANGLA VOICE
                # ============================
                voices = engine.getProperty('voices')
                selected_voice = None

                for v in voices:
                    name = v.name.lower()
                    if any(k in name for k in ["bangla", "bengali", "bn", "kalpana", "hemant"]):
                        selected_voice = v.id
                        print("✅ Bangla voice found:", v.name)
                        break

                # ============================
                # ⚠️ FALLBACK WARNING
                # ============================
                if not selected_voice:
                    print("⚠️ No Bangla voice found! Using default voice.")
                else:
                    engine.setProperty('voice', selected_voice)

                # ============================
                # 🎛️ SETTINGS
                # ============================
                engine.setProperty("rate", 180)   # slower for Bangla clarity
                engine.setProperty("volume", 1.0)

                # ============================
                # 🗣️ SPEAK
                # ============================
                engine.say(text)
                engine.runAndWait()

            except Exception as e:
                print("TTS ERROR:", e)

    threading.Thread(target=run).start()
pygame.mixer.init()
speech_lock = threading.Lock()

def speak(text: str):
    if not STATE["voice_enabled"]:
        return

    def run():
        with speech_lock:
            try:
                print("🎙 SPEAKING (BN):", text)

                audio_bytes = asyncio.run(generate_audio_bytes(text))

                play_audio_bytes(audio_bytes)

            except Exception as e:
                print("TTS ERROR:", e)

    threading.Thread(target=run, daemon=True).start()


# =========================================
# 🎧 GENERATE AUDIO IN MEMORY (NO FILE)
# =========================================
async def generate_audio_bytes(text):
    communicate = edge_tts.Communicate(
        text=text,
        voice="bn-BD-NabanitaNeural",
        rate="+15%"
    )

    audio_stream = b""

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_stream += chunk["data"]

    return audio_stream


# =========================================
# 🔊 PLAY FROM MEMORY (OBS READY)
# =========================================
def play_audio_bytes(audio_bytes):
    try:
        audio_file = io.BytesIO(audio_bytes)

        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()

        # wait until finished (important for OBS capture)
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

    except Exception as e:
        print("AUDIO ERROR:", e)
# =====================================================
# 🕷️ SELENIUM DRIVER
# =====================================================
def create_driver(url):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    driver.get(url)

    time.sleep(3)
    return driver


# =====================================================
# 🔥 SCRAPER LOOP
# =====================================================
async def scraper_loop_commentry(driver):
    seen = set()

    while ACTIVE_MATCH["running"]:
        try:
            #driver = ACTIVE_MATCH["driver"]

            if not driver:
                await asyncio.sleep(1)
                continue

            cards = driver.find_elements(By.CLASS_NAME, "cm-b-roundcard")

            for c in cards:
                try:
                    over = c.find_element(By.CLASS_NAME, "cm-b-over").text
                except:
                    over = ""

                try:
                    ball = c.find_element(By.CLASS_NAME, "cm-b-ballupdate").text
                except:
                    ball = ""

                try:
                    c1 = c.find_element(By.CLASS_NAME, "cm-b-comment-c1").text
                except:
                    c1 = ""

                try:
                    c2 = c.find_element(By.CLASS_NAME, "cm-b-comment-c2").text
                except:
                    c2 = ""

                text = f"{over} {ball} {c1} {c2}".strip()

                if len(text) < 3:
                    continue

                key = hash(text)

                if key in seen:
                    continue

                seen.add(key)

                final = director_ai(text)

                print("📡 EVENT:", final)

                await event_queue.put(final)

        except Exception as e:
            print("SCRAPER ERROR:", e)

        await asyncio.sleep(1)

async def scraper_loop_old():
    seen_comments = set()
    last_result = None

    while ACTIVE_MATCH["running"]:
        try:
            driver = ACTIVE_MATCH["driver"]

            if not driver:
                await asyncio.sleep(1)
                continue

            # =====================================================
            # 🎯 1. SCOREBOARD RESULT-BOX (ONLY THIS SECTION)
            # =====================================================
            try:
                result = driver.find_element(
                    By.CSS_SELECTOR,
                    ".live-score-card .team-result .result-box .font1"
                ).text.strip()
                if result:
                    print(result)
                    if result and result != last_result:
                        last_result = result

                        final = f"{result}"

                        print("🎯 RESULT:", final)

                        await event_queue.put(final)
                else:
                    result = driver.find_element(
                        By.CSS_SELECTOR,
                        ".live-score-card .team-result .result-box .font3"
                    ).text.strip()
                    print(result)
                    if result and result != last_result:
                        last_result = result

                        final = f"{result}"

                        print("🎯 RESULT:", final)

                        await event_queue.put(final)

            except:
                pass

            # =====================================================
            # 🟢 2. BALL-BY-BALL COMMENTARY
            # =====================================================
            """cards = driver.find_elements(By.CLASS_NAME, "cm-b-roundcard")

            for c in cards:
                try:
                    over = c.find_element(By.CLASS_NAME, "cm-b-over").text
                except:
                    over = ""

                try:
                    ball = c.find_element(By.CLASS_NAME, "cm-b-ballupdate").text
                except:
                    ball = ""

                try:
                    c1 = c.find_element(By.CLASS_NAME, "cm-b-comment-c1").text
                except:
                    c1 = ""

                try:
                    c2 = c.find_element(By.CLASS_NAME, "cm-b-comment-c2").text
                except:
                    c2 = ""

                text = f"{over} {ball} {c1} {c2}".strip()

                if len(text) < 3:
                    continue

                key = hash(text)

                if key in seen_comments:
                    continue

                seen_comments.add(key)

                final = director_ai(text)

                print("📡 COMMENT:", final)

                await event_queue.put(final)
            """
        except Exception as e:
            print("SCRAPER ERROR:", e)

        await asyncio.sleep(1)
def detect_event(value: str, batsmen, bowler):
    mapping = {
        "0": "DOT",
        "1": "SINGLE",
        "2": "DOUBLE",
        "3": "TRIPLE",
        "4": "FOUR",
        "6": "SIX",
        "Ball": "BOWLER_RUNUP",
        "Bowled":"BOWLED",
        "Over": "OVER_SUMMARY",
        "Maiden Over": "MAIDEN_OVER",
        "Time Out"   :"TIME_OUT",
        "Wide": "WIDE",
        "Caught Out":"CATCH",
        "Wicket": "WICKET",
        "Strategic Timeout": "STRATEGIC_TIMEOUT",
        
    }

    key = mapping.get(value)
    
    if key and key in COMMENTARY:
        return random.choice(COMMENTARY[key])
    
    return " "
    
def get_milestone_comment(name, runs):
    """Return milestone commentary for 50/100 runs."""
    if runs == 50:
        return f"🎉 কী দুর্দান্ত ব্যাটিং! {name} এখন হাফ সেঞ্চুরি (৫০ রান) পূর্ণ করেছে!"
    elif runs == 100:
        return f"🔥 অসাধারণ ইনিংস! {name} সেঞ্চুরি (১০০ রান) পূর্ণ করেছে! গ্যালারি উল্লাসে ফেটে পড়ছে!"
    return None

def detect_run_event(event):
    """
    Return run-based event
    """
    
    if event == "0":
        return "DOT"
    elif event == "1":
        return "SINGLE"
    elif event == "2":
        return "DOUBLE"
    elif event == "3":
        return "TRIPLE"
    elif event == "4":
        return "FOUR"
    elif event == "6":
        return "SIX"    
    return None
    
def detect_extra(event):
    if event=="Wide":
        return "WIDE"
    elif event == "No Ball":
        return "NO_BALL"
    elif event == "Bye":
        return "BYE"

# =====================================================
# 🎯 EVENT MAPS (FAST LOOKUP)
# =====================================================
RUN_EVENT_MAP = {
    "0": "DOT",
    "1": "SINGLE",
    "2": "DOUBLE",
    "3": "TRIPLE",
    "4": "FOUR",
    "6": "SIX"
}

EXTRA_EVENT_MAP = {
    "Wide": "WIDE",
    "No Ball": "NO_BALL",
    "Bye": "BYE"
}


# =====================================================
# 🎯 MILESTONE
# =====================================================
def get_milestone_comment(name, runs):
    milestone_map = {
        50: f"🎉 দারুণ ব্যাটিং! {name} হাফ সেঞ্চুরি পূর্ণ করলেন!",
        100: f"🔥 অসাধারণ! {name} সেঞ্চুরি পূর্ণ করেছেন!"
    }
    return milestone_map.get(runs)


# =====================================================
# 🎯 EVENT DETECTION (FAST)
# =====================================================
def detect_event(event):
    return RUN_EVENT_MAP.get(event) or EXTRA_EVENT_MAP.get(event)
# =====================================================
# 🎯 MAIN COMMENTARY ENGINE
# =====================================================
def generate_continuous_commentary(
    event,
    batsmen,
    bowler,
    runs,
    wickets,
    over,
    team1=None,
    team2=None,
    context=None
):
    parts = []

    # =====================================================
    # 🟢 1. BALL START (Bowler run-up)
    # =====================================================
    if event == "Ball":
        bowler_name = remove_first_part(clean_name(bowler["name"])) if bowler else ""
        return random.choice(COMMENTARY["BOWLER_RUNUP"]).format(bowler=bowler_name)

    # =====================================================
    # 🔴 2. WICKET (Highest priority)
    # =====================================================
    if event == "WICKET":
        parts.append(
            generate_wicket_commentary(
                runs,
                wickets,
                over,
                batsmen[0]['name'] if batsmen else None,
                context
            )
        )

    # =====================================================
    # 🟡 3. RUN / EXTRA EVENT
    # =====================================================
    detected = detect_event(event)

    if detected:
        parts.append(random.choice(COMMENTARY.get(detected, [""])))


    # =====================================================
    # 🟢 4. BATSMAN STATUS
    # =====================================================
    if batsmen:
        batsmen_lines = []

        for b in batsmen[:2]:
            batsmen_lines.append(
                f"{b['name']} {number_to_bangla_words(b['runs'])} রান"
            )

        parts.append(" | ".join(batsmen_lines) + " করছে")

        # 🎯 Milestone check
        for b in batsmen[:2]:
            milestone = get_milestone_comment(b["name"], b["runs"])
            if milestone:
                parts.append(milestone)

    # =====================================================
    # 🔵 5. OVER COMPLETE
    # =====================================================
    if event in ["Over", "Maiden Over"]:
        if event == "Maiden Over":
            parts.append(random.choice(COMMENTARY["MAIDEN_OVER"]))

        parts.append(
            f"{number_to_bangla_words(over)} ওভার শেষ। "
            f"স্কোর {number_to_bangla_words(runs)} রানে "
            f"{number_to_bangla_words(wickets)} উইকেট।"
        )

        # Welcome message (optional)
        if team1 and team2:
            parts.append(
                f"নতুন দর্শকদের স্বাগতম! {team1} বনাম {team2} ম্যাচে "
                f"বর্তমান স্কোর {number_to_bangla_words(runs)} রানে "
                f"{number_to_bangla_words(wickets)} উইকেট।"
            )

    # =====================================================
    # ⚡ FINAL OUTPUT
    # =====================================================
    return " ".join(filter(None, parts))
    
def generate_continuous_commentary2(events, batsmen, bowler, runs, wickets, over, team1=None, team2=None, context=None):
    """
    Generate a smooth, human-like cricket commentary for a sequence of events
    - events: list of strings (SIX, FOUR, WICKET, DOUBLE, SINGLE, DOT, WIDE, NO_BALL, OVER_COMPLETE)
    - batsmen: list of dicts [{'name':str,'runs':int}, ...]
    - runs: total runs
    - wickets: total wickets
    - over: current over (float)
    - team1, team2: optional team names for updates
    """
    #has_alpha = any(c.isalpha() for c in context)
    #has_digit = any(c.isdigit() for c in context)
    
    """status = None
    if has_alpha:
        status = context
        print("Context", context)"""
    
        
    parts = []
    if events =="Ball":
        commentary = random.choice(COMMENTARY["BOWLER_RUNUP"]).format(bowler=remove_first_part(clean_name(bowler["name"])))                                                       
        parts.append(commentary)           
        return " ".join(parts)
        
    # 1️⃣ WICKET has highest priority
    if "WICKET" in events:
        parts.append(generate_wicket_commentary(runs, wickets, over, batsmen[0]['name'] if batsmen else None, context))

    # 2️⃣ Scoring events (SIX, FOUR, DOUBLE, SINGLE, DOT)
    event = detect_run_event(events)    
    if event:
        print(events)
        parts.append(generate_event_commentary([event]))            
    
    
    # 3️⃣ Extras
    extra = detect_extra(events)
    if extra:
            parts.append(generate_event_commentary([extra]))
    
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
    
    
    if "Over" in events:
        over_comment = ""        
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
            
    if "Maiden Over" in events:
            over_comment = ""        
            commentary_text = random.choice(COMMENTARY["MAIDEN_OVER"])
            over_comment = commentary_text + f"{number_to_bangla_words(over)} ওভার শেষ। স্কোর এখন {number_to_bangla_words(runs)} রান, {number_to_bangla_words(wickets)} উইকেট।"    
            # 6️⃣ Welcome message and quick update for new viewers
            if team1 and team2:
                welcome_msg = (
                    f"যারা নতুন যুক্ত হয়েছেন, স্বাগতম! "
                    f"এই সময় {team1} বনাম {team2} ম্যাচে স্কোর {number_to_bangla_words(runs)} রানে {number_to_bangla_words(wickets)} উইকেট। "
                    f"{number_to_bangla_words(over)} ওভার শেষ হয়েছে, দলের সংগ্রহ ভালোভাবে এগুচ্ছে। ম্যাচে উত্তেজনা অব্যাহত!"
                )
                parts.append(welcome_msg) 
    return " ".join(parts)
    """"for extra in ["WIDE", "NO_BALL"]:
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
            parts.append(welcome_msg)     """

    # Combine all commentary parts naturally
    
    #return " ".join(parts)
  
async def scraper_loop_old_2():
    
    last_result = None

    while ACTIVE_MATCH["running"]:
        try:
            driver = ACTIVE_MATCH["driver"]

            if not driver:
                await asyncio.sleep(1)
                continue

            # =====================================================
            # 🎯 RESULT-BOX (OPTIMIZED SINGLE QUERY)
            # =====================================================
            result = ""

            try:
                # Get BOTH font1 + font3 at once (faster)
                elements = driver.find_elements(
                    By.CSS_SELECTOR,
                    ".live-score-card .team-result .result-box span"
                )

                for el in elements:
                    txt = el.text.strip()
                    if txt:
                        result = txt
                        break  # take first valid

            except Exception:
                result = ""

            # =====================================================
            # 🔁 UPDATE ONLY IF CHANGED
            # =====================================================
            if result and result != last_result:
                last_result = result

                print("🎯 RESULT:", result)
                
                await event_queue.put(detect_event(result))

        except Exception as e:
            print("SCRAPER ERROR:", e)

        # =====================================================
        # ⚡ FASTER BUT SAFE POLLING
        # =====================================================
        await asyncio.sleep(0.7)
        
def parse_players(driver):
    data = {
        "batsmen": [],
        "bowler": {}
    }

    try:
        container = driver.find_element(By.CLASS_NAME, "playing-batsmen-wrapper")

        # =====================================================
        # 🏏 GET ALL PLAYER BLOCKS
        # =====================================================
        players = container.find_elements(By.CLASS_NAME, "batsmen-partnership")

        for p in players:
            try:
                name = p.find_element(By.CSS_SELECTOR, ".batsmen-name p").text.strip()
                score = p.find_element(By.CSS_SELECTOR, ".batsmen-score p:nth-child(1)").text.strip()
                balls = p.find_element(By.CSS_SELECTOR, ".batsmen-score p:nth-child(2)").text.strip()

                # detect bowler block
                is_bowler = "bowler" in p.get_attribute("innerHTML")

                if is_bowler:
                    data["bowler"] = {
                        "name": name,
                        "figures": score,
                        "overs": balls
                    }
                else:
                    data["batsmen"].append({
                        "name": name,
                        "runs": score,
                        "balls": balls
                    })

            except:
                continue

    except Exception as e:
        print("PLAYER PARSE ERROR:", e)

    return data
    
async def scraper_loop_27_04():
    last_result = None
    last_players = ""

    while ACTIVE_MATCH["running"]:
        try:
            driver = ACTIVE_MATCH["driver"]

            if not driver:
                await asyncio.sleep(1)
                continue

            # =====================================================
            # 🎯 RESULT BOX
            # =====================================================
            result = ""

            try:
                elements = driver.find_elements(
                    By.CSS_SELECTOR,
                    ".live-score-card .team-result .result-box span"
                )

                for el in elements:
                    txt = el.text.strip()
                    if txt:
                        result = txt
                        break

            except:
                result = ""

            if result and result != last_result:
                last_result = result
                print("🎯 RESULT:", result)

                await event_queue.put(detect_event(result))

            # =====================================================
            # 🏏 PLAYERS PARSE
            # =====================================================
            players = parse_players(driver)

            if players and players.get("batsmen"):
                normalized_batsmen = []

                # -------------------------
                # 🟢 Normalize Batsmen
                # -------------------------
                for b in players["batsmen"]:
                    try:
                        normalized_batsmen.append({
                            "name": remove_first_part(clean_name(b["name"])),
                            "runs": int(re.search(r"\d+", b["runs"]).group()),
                            "balls": int(re.search(r"\d+", b["balls"]).group()),
                        })
                    except Exception as e:
                        print("Batsman Parse Error:", e)
                        continue

                batsmen_text = ", ".join(
                    f"{b['name']} {b['runs']}({b['balls']})"
                    for b in normalized_batsmen
                )

                # =====================================================
                # 🎯 Bowler (STRUCTURED)
                # =====================================================
                bowler_text = ""
                bowler_obj = {}

                bowler_data = players.get("bowler")

                if bowler_data:
                    try:
                        bowler_name = remove_first_part(clean_name(bowler_data["name"]))

                        # runs + wickets (e.g. "0-1")
                        match = re.search(r"(\d+)-(\d+)", bowler_data["figures"])
                        runs = int(match.group(1)) if match else 0
                        wickets = int(match.group(2)) if match else 0

                        # overs (e.g. "(0.4)")
                        overs_match = re.search(r"[\d.]+", bowler_data["overs"])
                        overs = float(overs_match.group()) if overs_match else 0.0

                        bowler_obj = {
                            "bowler": bowler_name,
                            "runs_conceded": runs,
                            "wickets": wickets,
                            "overs": overs
                        }

                        bowler_text = f"{bowler_name} {runs}-{wickets} ({overs})"

                    except Exception as e:
                        print("Bowler Parse Error:", e)

                # =====================================================
                # 🧾 FINAL OUTPUT
                # =====================================================
                final_text = f"{batsmen_text} | Bowler: {bowler_text}"               
                bowler = ""                
                if result =="Ball" and result != last_result:
                    last_result = result
                    commentary = random.choice(COMMENTARY["BOWLER_RUNUP"]).format(bowler=remove_first_part(clean_name(bowler_obj["bowler"])))                                               
                    print("🏏 PLAYERS:", final_text)

                    await event_queue.put(commentary)

        except Exception as e:
            print("SCRAPER ERROR:", e)

        # =====================================================
        # ⚡ FAST POLLING
        # =====================================================
        await asyncio.sleep(0.7)
        
def get_score_data(driver):
    try:
        elements = driver.find_elements(
            By.CSS_SELECTOR,
            ".live-score-card .team-score .runs span"
        )

        if len(elements) < 2:
            return None

        # -----------------------------
        # 🟢 Runs & Wickets (e.g. 49-4)
        # -----------------------------
        score_text = elements[0].text.strip()

        match = re.search(r"(\d+)-(\d+)", score_text)
        runs = int(match.group(1)) if match else 0
        wickets = int(match.group(2)) if match else 0

        # -----------------------------
        # 🔵 Overs + Balls (e.g. 7.3)
        # -----------------------------
        overs_text = elements[1].text.strip()

        over_match = re.search(r"(\d+)\.(\d+)", overs_text)

        if over_match:
            overs = int(over_match.group(1))   # full overs → 7
            balls = int(over_match.group(2))   # balls → 3
        else:
            # fallback (e.g. "7")
            overs = int(float(overs_text))
            balls = 0

        return {
            "runs": runs,
            "wickets": wickets,
            "overs": overs,
            "balls": balls
        }

    except Exception as e:
        print("SCORE PARSE ERROR:", e)
        return None
        
def get_result(driver):
    try:
        elements = driver.find_elements(
            By.CSS_SELECTOR,
            ".live-score-card .team-result .result-box span"
        )

        for el in elements:
            txt = el.text.strip()
            if txt:
                return txt
    except:
        pass

    return ""
    
def get_batsmen(players):
    result = []

    if not players or not players.get("batsmen"):
        return result

    for b in players["batsmen"]:
        try:
            result.append({
                "name": remove_first_part(clean_name(b["name"])),
                "runs": int(re.search(r"\d+", b["runs"]).group()),
                "balls": int(re.search(r"\d+", b["balls"]).group()),
            })
        except Exception as e:
            print("Batsman Parse Error:", e)

    return result
    
def get_bowler(players):
    if not players:
        return None

    bowler_data = players.get("bowler")

    if not bowler_data:
        return None

    try:
        name = remove_first_part(clean_name(bowler_data["name"]))

        match = re.search(r"(\d+)-(\d+)", bowler_data["figures"])
        runs = int(match.group(1)) if match else 0
        wickets = int(match.group(2)) if match else 0

        overs_match = re.search(r"[\d.]+", bowler_data["overs"])
        overs = float(overs_match.group()) if overs_match else 0.0

        return {
            "name": name,
            "runs_conceded": runs,
            "wickets": wickets,
            "overs": overs
        }

    except Exception as e:
        print("Bowler Parse Error:", e)
        return None
  
    
async def scraper_loop():
    last_result = None
    last_players = ""

    while ACTIVE_MATCH["running"]:
        try:
            driver = ACTIVE_MATCH["driver"]

            if not driver:
                await asyncio.sleep(1)
                continue

            # =====================================================
            # 🎯 RESULT
            # =====================================================
            result = get_result(driver)
            
            if result and result != last_result:
                last_result = result
                print("🎯 RESULT:", result)
                

                

                # =====================================================
                # 🏏 PLAYERS DATA
                # =====================================================
                players = parse_players(driver)

                batsmen = get_batsmen(players)
                bowler = get_bowler(players)
                score = get_score_data(driver)
                runs, wickets, over, ball = score
                
                if score:
                    print("📊 SCORE:", score)                    
                
                commentary = ""
                line = generate_continuous_commentary(
                            result,
                            batsmen,
                            bowler,
                            runs,
                            wickets,
                            over,
                            TEAM1,
                            TEAM2,
                            commentary
                        )
                print(line)
                if line:
                    await event_queue.put(line)
                #await scraper_loop_commentry(driver)
                #print(bowler)
                """if result =="Ball":
                   # commentary = random.choice(COMMENTARY["BOWLER_RUNUP"]).format(bowler=remove_first_part(clean_name(bowler["name"])))                                               
                
                    #print("🎯 commentary:", commentary)
                    await event_queue.put(line)
                else:
                    
                    await event_queue.put(detect_event(result,batsmen,bowler))"""
                # -------------------------
                # Format output (optional)
                # -------------------------
                """batsmen_text = ", ".join(
                    f"{b['name']} {b['runs']}({b['balls']})"
                    for b in batsmen
                )
                
                bowler_text = ""
                if bowler:
                    bowler_text = f"{bowler['name']} {bowler['runs_conceded']}-{bowler['wickets']} ({bowler['overs']})"

                final_text = f"{batsmen_text} | Bowler: {bowler_text}"

                if final_text and final_text != last_players:
                    last_players = final_text

                    print("🏏 PLAYERS:", final_text)

                    await event_queue.put(final_text)"""

        except Exception as e:
            print("SCRAPER ERROR:", e)

        await asyncio.sleep(0.7)
# =====================================================
# 🎯 EVENT WORKER
# =====================================================
async def event_worker():
    while True:
        text = await event_queue.get()
#text= director_ai(text)
        print("LIVE:", text)
            
        await broadcast(text)
        
        speak(text)   # 🔥 OBS-compatible TTS


# =====================================================
# 🏟️ START MATCH
# =====================================================
def start_match(url: str):
    url = url.strip()

    if not re.match(r"^https?://", url):
        print("INVALID URL")
        return

    print("🏟️ START MATCH:", url)

    ACTIVE_MATCH["running"] = False
    time.sleep(1)

    if ACTIVE_MATCH["driver"]:
        try:
            ACTIVE_MATCH["driver"].quit()
        except:
            pass

    driver = create_driver(url)

    ACTIVE_MATCH["url"] = url
    ACTIVE_MATCH["driver"] = driver
    ACTIVE_MATCH["running"] = True

    asyncio.create_task(scraper_loop())


# =====================================================
# 📡 WEBSOCKET
# =====================================================
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)

    try:
        while True:
            data = await websocket.receive_text()

            if data == "mute":
                STATE["voice_enabled"] = False

            elif data == "unmute":
                STATE["voice_enabled"] = True

            elif data.startswith("force:"):
                url = data.split(":", 1)[1].strip()
                start_match(url)
                await websocket.send_text("MATCH STARTED")

    except WebSocketDisconnect:
        clients.remove(websocket)


# =====================================================
# 🚀 STARTUP
# =====================================================
@app.on_event("startup")
async def startup():
    asyncio.create_task(event_worker())
    print("🚀 SYSTEM READY (OBS AUDIO FIXED)")