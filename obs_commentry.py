from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import asyncio
import edge_tts
import os

from obswebsocket import obsws, requests


# -------------------------------
# 🔗 OBS CONFIG
# -------------------------------
OBS_HOST = "localhost"
OBS_PORT = 4455
OBS_PASSWORD = "3dTPh3QRd8qvZrXr"

SOURCE_NAME = "CommentaryAudio"
AUDIO_FILE = "C:/cricket_voices/live_commentary.mp3"

ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
ws.connect()


def play_audio():
    ws.call(requests.TriggerMediaInputAction(
        inputName=SOURCE_NAME,
        mediaAction="OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"
    ))


# -------------------------------
# 🎙️ EDGE TTS (FAST STREAM)
# -------------------------------
async def generate_voice(text):
    communicate = edge_tts.Communicate(
        text=text,
        voice="en-GB-RyanNeural",   # 🔥 best for commentary
        rate="+10%",
        pitch="+2Hz"
    )
    await communicate.save(AUDIO_FILE)


def speak(text):
    try:
        asyncio.run(generate_voice(text))  # ⚡ fast generation
        play_audio()                      # 🔥 instant OBS play
    except Exception as e:
        print("TTS Error:", e)


# -------------------------------
# 🧠 Commentary Generator
# -------------------------------
def generate_commentary(text):
    t = text.upper()

    if "SIX" in t:
        return "OH MY WORD! That has been smashed into the stands! What a massive six!"
    elif "FOUR" in t:
        return "Brilliant shot! Timed to perfection and races away for four!"
    elif "OUT" in t:
        return "HE'S GONE! That's a huge wicket at a crucial moment!"
    elif "WIDE" in t:
        return "That is down the leg side, called a wide."
    elif "NO BALL" in t:
        return "No ball! Free hit coming up!"
    elif "50" in t:
        return "What a fantastic innings! He brings up his half century!"
    else:
        return text


# -------------------------------
# 🌐 SELENIUM SETUP
# -------------------------------
URL = "https://crex.com/cricket-live-score/rr-vs-srh-21st-match-indian-premier-league-2026-match-updates-1182"

options = Options()
options.add_argument("--headless=new")

driver = webdriver.Chrome(options=options)
driver.get(URL)

seen = set()

try:
    while True:
        elements = driver.find_elements(By.CLASS_NAME, "cm-b-comment-c2")
        elements = elements[::-1]

        for el in elements:
            try:
                text = el.text.strip()

                if text and text not in seen:
                    seen.add(text)

                    commentary = generate_commentary(text)

                    print(commentary)

                    # 🔥 ULTRA FAST VOICE → OBS
                    speak(commentary)

                    time.sleep(0.2)

            except:
                continue

        time.sleep(1)

except KeyboardInterrupt:
    print("Stopped.")

finally:
    driver.quit()
    ws.disconnect()