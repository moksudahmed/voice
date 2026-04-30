from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import asyncio
import threading
import time
import re
import random
import io

import pygame
import edge_tts

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

from commentry_dic import COMMENTARY
from utill import number_to_bangla_words
import requests
from bs4 import BeautifulSoup
# =====================================================
# ⚙️ CONFIG
# =====================================================
TEAM1 = "নিউজিল্যান্ড"
TEAM2 = "বাংলাদেশ"
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

BREAK_EVENT_MAP = {
    "Innings Break": "INNINGS_BREAK",
    "Drinks Break": "DRINKS_BREAK",
    "Tea Break": "TEA_BREAK",
    "Lunch Break": "LUNCH_BREAK",
    "Rain Break": "RAIN_BREAK",
    "Rain Break (Delayed)": "RAIN_DELAY"
}

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def home():
    return FileResponse("static/index.html")

@app.get("/matches")
def get_matches():
    try:
        url = "https://crex.com/"
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        matches = []

        # Generic extraction (CREX uses dynamic classes, so we scan text blocks)
        for tag in soup.find_all(["a", "div", "span"]):
            text = tag.get_text(strip=True)

            if not text:
                continue

            # filter only cricket match-like strings
            if (
                "vs" in text.lower()
                and len(text) < 120
                and any(x in text.lower() for x in ["t20", "odi", "test", "league", "ipl"])
            ):
                matches.append({
                    "title": text,
                    "url": "https://crex.com/"
                })

        # remove duplicates
        seen = set()
        unique = []

        for m in matches:
            if m["title"] not in seen:
                seen.add(m["title"])
                unique.append(m)

        return unique[:20]

    except Exception as e:
        return {"error": str(e)}
# =====================================================
# 🌐 GLOBAL STATE
# =====================================================
clients = set()

STATE = {
    "voice_enabled": True
}

event_queue = asyncio.Queue()

ACTIVE_MATCH = {
    "driver": None,
    "running": False
}


def remove_first_part(name):
    parts = name.split(" ", 1)
    return parts[1] if len(parts) > 1 else name


# =====================================================
# 🧠 HELPERS
# =====================================================
def clean_name(name):
    return " ".join(name.strip().split()[-2:])


def safe_int(x):
    try:
        return int(re.search(r"\d+", str(x)).group())
    except:
        return 0


def safe_float(x):
    try:
        return float(re.search(r"[\d.]+", str(x)).group())
    except:
        return 0.0


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
# 🔊 TTS (EDGE + OBS SAFE)
# =====================================================
pygame.mixer.init()
speech_lock = threading.Lock()


async def generate_audio(text):
    comm = edge_tts.Communicate(text=text, voice="bn-BD-NabanitaNeural")
    audio = b""

    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]

    return audio


def play_audio(audio_bytes):
    try:
        audio_file = io.BytesIO(audio_bytes)
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
    except:
        pass


def speak(text):
    if not STATE["voice_enabled"]:
        return

    def run():
        with speech_lock:
            try:
                audio = asyncio.run(generate_audio(text))
                play_audio(audio)
            except:
                pass

    threading.Thread(target=run, daemon=True).start()


# =====================================================
# 🧷 SELENIUM DRIVER
# =====================================================
def create_driver(url):
    opt = Options()
    opt.add_argument("--headless=new")
    opt.add_argument("--no-sandbox")
    opt.add_argument("--disable-gpu")
    opt.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=opt)
    driver.get(url)
    time.sleep(3)
    return driver


# =====================================================
# 📊 SCORE PARSER
# =====================================================
def get_score(driver):
    try:
        spans = driver.find_elements(
            By.CSS_SELECTOR,
            ".live-score-card .team-score .runs span"
        )

        if len(spans) < 2:
            return None

        score = spans[0].text.strip()
        over = spans[1].text.strip()

        m = re.search(r"(\d+)-(\d+)", score)
        runs = int(m.group(1)) if m else 0
        wickets = int(m.group(2)) if m else 0

        m2 = re.search(r"(\d+)\.(\d+)", over)
        overs = int(m2.group(1)) if m2 else 0

        return runs, wickets, overs

    except:
        return None


# =====================================================
# 🏏 PLAYER PARSER
# =====================================================
def parse_players(driver):
    try:
        wrapper = driver.find_element(By.CSS_SELECTOR, ".playing-batsmen-wrapper")
    except:
        return None

    batsmen = []
    bowler = None

    try:
        cards = wrapper.find_elements(By.CSS_SELECTOR, ".batsmen-partnership")

        for c in cards:
            try:
                name = c.find_element(By.CSS_SELECTOR, ".batsmen-name p").text.strip()
                stats = c.find_elements(By.CSS_SELECTOR, ".batsmen-score p")

                if len(stats) >= 2:
                    batsmen.append({
                        "name": name,
                        "runs": safe_int(stats[0].text),
                        "balls": safe_int(stats[1].text)
                    })
            except:
                continue
    except:
        pass

    try:
        bname = wrapper.find_element(
            By.CSS_SELECTOR,
            ".batsmen-score.bowler + .batsmen-name p"
        ).text.strip()

        bstats = wrapper.find_elements(
            By.CSS_SELECTOR,
            ".batsmen-score.bowler p"
        )

        bowler = {
            "name": bname,
            "figures": bstats[0].text if len(bstats) > 0 else "0-0",
            "overs": bstats[1].text if len(bstats) > 1 else "0.0"
        }

    except:
        bowler = None

    return {"batsmen": batsmen, "bowler": bowler}


# =====================================================
# 🎙 COMMENTARY ENGINE
# =====================================================
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
    runs=None,
    wickets=None,
    over=None,
    team1=None,
    team2=None,
    context=None
):
    parts = []
    
    if event in BREAK_EVENT_MAP:
        templates = COMMENTARY.get(BREAK_EVENT_MAP[event], [])
        template = random.choice(templates)

        # Safe formatting (avoid crash if missing placeholders)
        return template.format(
            team=team1 or "",
            runs=runs or "",
            wickets=wickets or ""
        )

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
    
def generate_commentary(event, batsmen, bowler, runs, wickets, overs):
    parts = []

    # RUN EVENTS
    if event in COMMENTARY:
        parts.append(random.choice(COMMENTARY[event]))

    # BATSMEN STATUS
    if batsmen:
        parts.append(
            " | ".join(
                f"{b['name']} {b['runs']}({b['balls']})"
                for b in batsmen[:2]
            )
        )

    # SCORE UPDATE
    parts.append(
        f"{number_to_bangla_words(runs)} রানে {number_to_bangla_words(wickets)} উইকেট"
    )

    return " ".join(parts)


# =====================================================
# 🔥 SCRAPER LOOP (MAIN ENGINE)
# =====================================================

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
            runs_raw = b.get("runs", 0)
            balls_raw = b.get("balls", 0)

            # ✅ SAFE CONVERSION (no regex on int)
            runs = int(runs_raw) if isinstance(runs_raw, (int, float)) else safe_int(runs_raw)
            balls = int(balls_raw) if isinstance(balls_raw, (int, float)) else safe_int(balls_raw)

            name = b.get("name", "")
            if isinstance(name, (int, float)):
                name = str(name)

            result.append({
                "name": remove_first_part(clean_name(name)),
                "runs": runs,
                "balls": balls,
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
# 📡 EVENT WORKER
# =====================================================
async def event_worker():
    while True:
        msg = await event_queue.get()
        await broadcast(msg)
        speak(msg)


# =====================================================
# 🏟 START MATCH
# =====================================================
def start_match(url):
    ACTIVE_MATCH["running"] = False
    time.sleep(1)

    if ACTIVE_MATCH["driver"]:
        try:
            ACTIVE_MATCH["driver"].quit()
        except:
            pass

    ACTIVE_MATCH["driver"] = create_driver(url)
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
                url = data.split(":", 1)[1]
                start_match(url)

    except WebSocketDisconnect:
        clients.remove(websocket)


# =====================================================
# 🚀 STARTUP
# =====================================================
@app.on_event("startup")
async def startup():
    asyncio.create_task(event_worker())
    print("🚀 SYSTEM READY (FINAL STABLE VERSION)")