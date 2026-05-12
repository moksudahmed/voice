import asyncio
import aiohttp
import json
from playwright.async_api import async_playwright

API_URL = "https://api.goscorer.com/api/v3/getSV3?key=11RY"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

MATCH_URL = "https://crex.com/cricket-live-score/br-vs-sgr-1st-match-afghanistan-national-t20-cup-2026-match-updates-11RY"


# =========================
# API FETCH
# =========================
async def fetch_api(session):
    async with session.get(API_URL, headers=HEADERS) as res:
        return await res.json()


# =========================
# FULL UI SCRAPER (ALL DATA)
# =========================
async def scrape_full_ui():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(MATCH_URL, wait_until="networkidle")

        # wait for Angular to fully render
        await page.wait_for_timeout(5000)

        # =========================
        # 1. SCOREBOARD SECTION
        # =========================
        scoreboard_text = await page.evaluate("""
            () => {
                const el = document.querySelector('.scoreboard, .match-score, .live-score');
                return el ? el.innerText : null;
            }
        """)

        # =========================
        # 2. TEAM RESULT (YOUR TARGET)
        # =========================
        team_result = await page.evaluate("""
            () => {
                const el = document.querySelector('.team-result .result-box span.font3');
                return el ? el.innerText : null;
            }
        """)

        # =========================
        # 3. ALL MATCH EVENTS
        # =========================
        events = await page.evaluate("""
            () => {
                let items = [];
                document.querySelectorAll('.event, .commentary, .live-text, .ball-detail').forEach(e => {
                    items.push(e.innerText);
                });
                return items;
            }
        """)

        # =========================
        # 4. COMMENTARY BLOCKS
        # =========================
        commentary = await page.evaluate("""
            () => {
                let c = [];
                document.querySelectorAll('.commentary-item, .text-commentary').forEach(e => {
                    c.push(e.innerText);
                });
                return c;
            }
        """)

        # =========================
        # 5. ALL RAW TEXT (FALLBACK)
        # =========================
        body_text = await page.evaluate("""
            () => document.body.innerText
        """)

        await browser.close()

        return {
            "scoreboard": scoreboard_text,
            "team_result": team_result,
            "events": events,
            "commentary": commentary,
            "raw_page_text": body_text[:5000]  # limit for safety
        }


# =========================
# CLEAN MERGER ENGINE
# =========================
def merge_data(api, ui):
    return {
        "api": {
            "team1": api.get("j"),
            "team2": api.get("k"),
            "current": api.get("i"),
            "run_rate": api.get("s"),
            "format": api.get("fo"),
        },

        "ui": {
            "scoreboard": ui.get("scoreboard"),
            "event": ui.get("team_result"),
            "events": ui.get("events"),
            "commentary": ui.get("commentary")
        }
    }


# =========================
# MAIN LOOP (REAL-TIME)
# =========================
async def main():
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                api_data = await fetch_api(session)
                ui_data = await scrape_full_ui()

                full = merge_data(api_data, ui_data)

                print("\n" + "=" * 60)
                print("🏏 TEAM 1:", full["api"]["team1"])
                print("🏏 TEAM 2:", full["api"]["team2"])
                print("📊 SCORE:", full["api"]["current"])
                print("⚡ RR:", full["api"]["run_rate"])

                print("\n🖥 UI EVENT:", full["ui"]["event"])

                print("\n🎯 EVENTS SAMPLE:")
                print(full["ui"]["events"][:3])

                print("=" * 60)

            except Exception as e:
                print("ERROR:", str(e))

            await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())