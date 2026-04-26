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
import pyttsx3

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
async def scraper_loop2():
    seen = set()

    while ACTIVE_MATCH["running"]:
        try:
            driver = ACTIVE_MATCH["driver"]

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
def detect_event(value: str):
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
        "Strategic Timeout": "STRATEGIC_TIMEOUT"
    }

    key = mapping.get(value)

    if key and key in COMMENTARY:
        return random.choice(COMMENTARY[key])

    return " "
    
async def scraper_loop():
    
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