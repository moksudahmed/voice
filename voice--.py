"""
Cricket Live Commentary Bot
Scrapes live scores from CREX and generates Bengali TTS commentary via EdgeTTS.
"""

import asyncio
import json
import os
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import edge_tts
from playwright.async_api import async_playwright

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
CREX_URL = "https://crex.com/scoreboard/10SV/2F1/8th-Match/MC/M9/icn-vs-ing-8th-match-legends-league-cricket-2026/live"
OUTPUT_FILE = Path("C:/cricket_voices/score.json")
VOICE_FOLDER = Path("C:/cricket_voices/")
VOICE = "bn-BD-NabanitaNeural"
REFRESH_INTERVAL = 1  # seconds

# ─────────────────────────────────────────
# COMMENTARY BANK
# ─────────────────────────────────────────
COMMENTARY: dict[str, list[str]] = {
    "DOT":           ["ডট বল", "দারুণ বল, কোনো রান নেই", "ব্যাটসম্যান ডিফেন্স করেছেন",
                      "চমৎকার লাইন ও লেংথ", "বোলারের দারুণ বল"],
    "SINGLE":        ["এক রান নেওয়া হয়েছে", "সহজ সিঙ্গেল", "স্ট্রাইক রোটেট করলেন ব্যাটসম্যান"],
    "DOUBLE":        ["দুই রান সম্পন্ন", "দারুণ রানিং বিটুইন দ্য উইকেট"],
    "TRIPLE":        ["তিন রান নেওয়া হয়েছে", "দারুণ দৌড়ে তিন রান"],
    "FOUR":          ["চার! অসাধারণ শট", "গ্যাপ খুঁজে পেল ব্যাটসম্যান",
                      "চমৎকার বাউন্ডারি", "দারুণ টাইমিং"],
    "SIX":           ["ছক্কা! বল উড়ে গেল গ্যালারিতে", "বিশাল ছক্কা", "অসাধারণ পাওয়ার হিট"],
    "WICKET":        ["আউট! বড় উইকেট", "ব্যাটসম্যান ফিরে যাচ্ছেন", "দারুণ ব্রেকথ্রু"],
    "OVER_COMPLETE": ["ওভার শেষ", "একটি ওভার সম্পন্ন হয়েছে"],
    "NO_BALL":       ["নো বল!", "এক্সট্রা রান, এবং ফ্রি হিট পাবে ব্যাটসম্যান"],
    "WIDE":          ["ওয়াইড বল", "বোলারের লাইন মিস"],
    "FREE_HIT":      ["ফ্রি হিট! সুযোগ ব্যাটসম্যানের"],
}

RUN_TO_EVENT = {0: "DOT", 1: "SINGLE", 2: "DOUBLE", 3: "TRIPLE", 4: "FOUR", 6: "SIX"}


# ─────────────────────────────────────────
# STATE
# ─────────────────────────────────────────
@dataclass
class MatchState:
    runs: int = 0
    wickets: int = 0
    over: int = 0
    ball: int = 0
    free_hit_pending: bool = False
    last_lines: dict[str, str] = field(default_factory=dict)
    initialized: bool = False


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def pick_line(event: str, state: MatchState) -> Optional[str]:
    """Return a non-repeating random commentary line for the event."""
    base = event.removeprefix("FREE_HIT_")
    pool = COMMENTARY.get(base)
    if not pool:
        return None

    last = state.last_lines.get(base)
    candidates = [l for l in pool if l != last] or pool
    line = random.choice(candidates)
    state.last_lines[base] = line

    return ("ফ্রি হিট! " + line) if event.startswith("FREE_HIT_") else line


def parse_score(text: str) -> Optional[tuple[int, int, int, int]]:
    """Extract (runs, wickets, over, ball) from raw page text."""
    score = re.search(r"(\d+)\s*-\s*(\d+)", text)
    overs = re.search(r"(\d+)\.(\d+)", text)
    if not score:
        return None
    return (
        int(score.group(1)),
        int(score.group(2)),
        int(overs.group(1)) if overs else 0,
        int(overs.group(2)) if overs else 0,
    )


def detect_event(
    new: tuple[int, int, int, int],
    commentary: str,
    state: MatchState,
) -> str:
    """Compare new snapshot with previous state and return event name."""
    runs, wickets, over, ball = new

    if not state.initialized:
        state.runs, state.wickets, state.over, state.ball = runs, wickets, over, ball
        state.initialized = True
        return "NONE"

    ball_advanced = (over, ball) != (state.over, state.ball)
    run_diff = runs - state.runs
    event = "NONE"

    if wickets > state.wickets:
        event = "WICKET"
    elif over > state.over:
        event = "OVER_COMPLETE"
    elif ball_advanced:
        c = commentary
        if "no ball" in c:
            event = "NO_BALL"
            state.free_hit_pending = True
        elif "wide" in c:
            event = "WIDE"
        elif "free hit" in c:
            event = "FREE_HIT"
        else:
            event = RUN_TO_EVENT.get(run_diff, "RUNS" if run_diff > 0 else "DOT")

    # Wrap with FREE_HIT prefix if previous ball was a no-ball
    if state.free_hit_pending and event not in {"NO_BALL", "FREE_HIT", "NONE"}:
        event = "FREE_HIT_" + event
        state.free_hit_pending = False

    # Update state
    state.runs, state.wickets, state.over, state.ball = runs, wickets, over, ball
    return event


def write_json(runs: int, wickets: int, over: int, ball: int, event: str) -> None:
    """Atomically write score JSON to disk."""
    VOICE_FOLDER.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_FILE.with_suffix(".tmp")
    data = {"runs": runs, "wickets": wickets, "over": over, "ball": ball, "event": event}
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(OUTPUT_FILE)


# ─────────────────────────────────────────
# VOICE GENERATION
# ─────────────────────────────────────────
async def speak(event: str, text: str) -> None:
    """Generate TTS and atomically save to mp3."""
    VOICE_FOLDER.mkdir(parents=True, exist_ok=True)
    final = VOICE_FOLDER / f"{event}.mp3"
    tmp = final.with_suffix(".mp3.tmp")
    try:
        await edge_tts.Communicate(text, VOICE).save(str(tmp))
        tmp.replace(final)
        print(f"🎙  [{event}] {text}")
    except Exception as exc:
        print(f"⚠️  TTS failed for {event}: {exc}")
        tmp.unlink(missing_ok=True)


# ─────────────────────────────────────────
# SCRAPER
# ─────────────────────────────────────────
async def get_commentary(page) -> str:
    try:
        return (await page.locator("div[class*='commentary']").first.inner_text()).lower()
    except Exception:
        return ""


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
async def main() -> None:
    state = MatchState()
    print("🚀 Cricket Commentary Bot started")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(CREX_URL)

        while True:
            try:
                await page.reload()
                body = await page.inner_text("body")
                score = parse_score(body)

                if score is None:
                    await asyncio.sleep(REFRESH_INTERVAL)
                    continue

                runs, wickets, over, ball = score
                commentary = await get_commentary(page)
                event = detect_event(score, commentary, state)
                write_json(runs, wickets, over, ball, event)

                if event != "NONE":
                    line = pick_line(event, state)
                    if line:
                        # Fire-and-forget TTS so scraping doesn't stall
                        asyncio.create_task(speak(event, line))

            except Exception as exc:
                print(f"❌ Loop error: {exc}")

            await asyncio.sleep(REFRESH_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())