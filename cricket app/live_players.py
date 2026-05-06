from fastapi import FastAPI
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import asyncio

app = FastAPI()

URL = "https://crex.com/cricket-live-score/pbks-vs-srh-49th-match-indian-premier-league-2026-match-updates-118U"


# =========================
# PARSER FUNCTION (PURE HTML)
# =========================
def parse_players(html: str):
    soup = BeautifulSoup(html, "html.parser")

    players = {
        "batsmen": [],
        "bowler": None
    }

    wrappers = soup.select(".batsmen-partnership")

    for box in wrappers:
        name_tag = box.select_one(".batsmen-name p")
        runs_tags = box.select(".batsmen-score p")
        img_tag = box.select_one("img")

        name = name_tag.text.strip() if name_tag else None
        runs = runs_tags[0].text.strip() if len(runs_tags) > 0 else None
        balls = runs_tags[1].text.strip("()") if len(runs_tags) > 1 else None
        img = img_tag["src"] if img_tag and img_tag.has_attr("src") else None

        # detect bowler
        is_bowler = "bowler" in box.get("class", []) or box.select_one(".batsmen-score.bowler")

        player = {
            "name": name,
            "runs": runs,
            "balls": balls,
            "image": img
        }

        if is_bowler:
            players["bowler"] = player
        else:
            players["batsmen"].append(player)

    return players


# =========================
# SCRAPER (ASYNC PLAYWRIGHT)
# =========================
async def scrape_players(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("🌐 Live Players VISITING:", url)

        await page.goto(url, timeout=60000)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3000)

        # ✅ ONLY extract required section
        html = await page.inner_html(".playing-batsmen-wrapper")

        await browser.close()

        return parse_players(html)


# =========================
# API ENDPOINT
# =========================
