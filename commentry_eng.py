from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
from gtts import gTTS
from playsound import playsound
import os
import uuid


URL = "https://crex.com/cricket-live-score/rr-vs-srh-21st-match-indian-premier-league-2026-match-updates-1182"


# -------------------------------
# 🎙️ English Commentary Generator
# -------------------------------
def generate_english_commentary(text):
    t = text.upper()

    if "SIX" in t:
        return "Oh wow! That is massive! The ball sails into the stands for a huge six!"
    elif "FOUR" in t:
        return "Beautiful shot! Timed perfectly and it races away to the boundary for four!"
    elif "OUT" in t:
        return "That is out! A big breakthrough at this stage of the game!"
    elif "WIDE" in t:
        return "That is down the leg side, and the umpire signals a wide."
    elif "NO BALL" in t:
        return "No ball called! That will be a free hit."
    elif "50" in t:
        return "What a शानदार innings! He brings up his half-century!"
    else:
        return text  # fallback


# -------------------------------
# 🔊 Text → Voice (English)
# -------------------------------
def speak(text):
    try:
        filename = f"voice_{uuid.uuid4().hex}.mp3"

        tts = gTTS(text=text, lang='en')
        tts.save(filename)

        playsound(filename)

        time.sleep(0.5)  # prevent cut-off
        os.remove(filename)

    except Exception as e:
        print("Audio Error:", e)


# -------------------------------
# 🌐 Selenium Setup
# -------------------------------
options = Options()
options.add_argument("--headless=new")

driver = webdriver.Chrome(options=options)
driver.get(URL)

seen = set()

try:
    while True:
        elements = driver.find_elements(By.CLASS_NAME, "cm-b-comment-c2")

        elements = elements[::-1]  # oldest → newest

        new_found = False

        for el in elements:
            try:
                text = el.text.strip()

                if text and text not in seen:
                    seen.add(text)
                    new_found = True

                    eng_commentary = generate_english_commentary(text)

                    print("RAW :", text)
                    print("AI  :", eng_commentary)
                    print("-" * 60)

                    # 🔊 Speak English commentary
                    speak(eng_commentary)

            except:
                continue

        if not new_found:
            print("⏳ No new update...")

        time.sleep(2)

except KeyboardInterrupt:
    print("Stopped.")

finally:
    driver.quit()