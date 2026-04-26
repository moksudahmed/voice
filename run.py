from playwright.sync_api import sync_playwright
import re
import json
import time
import random
import sys
from datetime import datetime
import hashlib

from commentry import (
    generate_wicket_commentary,
    generate_event_commentary,
    generate_full_commentary
)
from voice import speak
from game_status import detect_game_status
from commentry_dic import WELCOME_COMMENTARY_TEMPLATES


# ================= CONFIG =================
CREX_URL = "https://crex.com/cricket-live-score/csk-vs-kkr-22nd-match-indian-premier-league-2026-match-updates-1183"
OUTPUT_FILE = "C:/cricket_voices/score.json"

TEAM1 = "সানরাইজার্স হায়দরাবাদ"
TEAM2 = "রাজস্থান রয়্যালস"

REFRESH_INTERVAL = 1


# ================= STATE =================
last_runs = last_wickets = last_over = last_ball = None
last_hash = None


# ================= HELPERS =================

def safe_locator(page, selector):
    try:
        return page.locator(selector).first.inner_text(timeout=5000)
    except:
        return None


def get_live_data(page):
    return {
        "score": safe_locator(page, "div[class*='score']"),
        "commentary": safe_locator(page, "div[class*='commentary']")
    }


def parse_score(text):
    if not text:
        return None

    match = re.search(r'(\d+)[-/](\d+).*?(\d+)\.(\d)', text)
    if not match:
        return None

    return (
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        int(match.group(4))
    )


def detect_run(diff):
    return {
        0: "DOT",
        1: "SINGLE",
        2: "DOUBLE",
        3: "TRIPLE",
        4: "FOUR"
    }.get(diff, "SIX" if diff >= 6 else None)


def detect_event(runs, wickets, over, ball, text=""):
    global last_runs, last_wickets, last_over, last_ball

    if last_runs is None:
        last_runs, last_wickets, last_over, last_ball = runs, wickets, over, ball
        return []

    events = []

    run_diff = runs - last_runs
    wicket_diff = wickets - last_wickets
    over_changed = over > last_over

    if over_changed:
        events.append("OVER_COMPLETE")

    if wicket_diff > 0:
        events.append("WICKET")
    else:
        if run_diff > 0:
            e = detect_run(run_diff)
            if e:
                events.append(e)
        else:
            events.append("DOT")

    last_runs, last_wickets, last_over, last_ball = runs, wickets, over, ball
    return list(dict.fromkeys(events))


def write_json(runs, wickets, over, ball, event):
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "runs": runs,
                "wickets": wickets,
                "over": over,
                "ball": ball,
                "event": event
            }, f, indent=4)
    except Exception as e:
        print("JSON error:", e)


def generate_commentary(events, runs, wickets, over):
    parts = []

    if "WICKET" in events:
        parts.append(generate_wicket_commentary(runs, wickets, over, None))

    for e in ["SIX", "FOUR", "DOUBLE", "SINGLE", "DOT"]:
        if e in events:
            parts.append(generate_event_commentary([e]))
            break

    if "OVER_COMPLETE" in events:
        parts.append(f"{over} ওভার শেষে স্কোর {runs}-{wickets}")

    return " ".join(parts)


def welcome():
    msg = random.choice(WELCOME_COMMENTARY_TEMPLATES)
    speak("WELCOME", msg.format(team1=TEAM1, team2=TEAM2))


# ================= MAIN =================

def main():
    global last_hash

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(CREX_URL, timeout=60000)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)

        print("🚀 SYSTEM STARTED")

        welcome()

        try:
            while True:
                try:
                    data = get_live_data(page)

                    score_data = parse_score(data["score"])

                    if not score_data:
                        print("⚠️ No score yet...")
                        time.sleep(2)
                        continue

                    runs, wickets, over, ball = score_data

                    # 🔥 duplicate protection
                    current_hash = hashlib.md5(
                        f"{runs}-{wickets}-{over}-{ball}".encode()
                    ).hexdigest()

                    if current_hash == last_hash:
                        time.sleep(REFRESH_INTERVAL)
                        continue

                    last_hash = current_hash

                    events = detect_event(
                        runs, wickets, over, ball,
                        data["commentary"] or ""
                    )

                    if not events:
                        continue

                    line = generate_commentary(events, runs, wickets, over)

                    if line:
                        print(f"🎙 {line}")
                        speak(events[0], line)

                        write_json(runs, wickets, over, ball, events[0])

                    print(f"📊 {runs}-{wickets} ({over}.{ball}) | {events}")

                except Exception as loop_error:
                    print("⚠️ Loop error:", loop_error)
                    page.reload()
                    page.wait_for_timeout(3000)

                time.sleep(REFRESH_INTERVAL)

        except KeyboardInterrupt:
            print("\n👋 Stopped manually")

        browser.close()


if __name__ == "__main__":
    main()