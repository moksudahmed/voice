import asyncio
import re
import json
from playwright.async_api import async_playwright


# =========================
# SAFE CONVERTERS
# =========================
def to_int(v, d=0):
    try:
        return int(str(v).strip())
    except:
        return d


def to_float(v, d=0.0):
    try:
        return float(str(v).strip())
    except:
        return d


# =========================
# GLOBAL STORAGE FOR API DATA
# =========================
captured_api_data = None


# =========================
# INTERCEPT NETWORK RESPONSE
# =========================
async def intercept_responses(route, request):
    global captured_api_data

    await route.continue_()

    try:
        if "score" in request.url or "match" in request.url or "innings" in request.url:
            response = await request.response()
            if response:
                data = await response.json()
                captured_api_data = data
    except:
        pass


# =========================
# FETCH PAGE + CAPTURE API
# =========================
async def get_page_html(url: str):
    global captured_api_data
    captured_api_data = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # listen network responses
        page.on("response", lambda response: asyncio.create_task(handle_response(response)))

        await page.goto(url, timeout=120000, wait_until="domcontentloaded")
        await page.wait_for_timeout(8000)

        html = await page.content()
        await browser.close()

        return html


# =========================
# CAPTURE JSON FROM NETWORK
# =========================
async def handle_response(response):
    global captured_api_data

    try:
        url = response.url.lower()

        if any(k in url for k in ["score", "match", "innings", "scorecard"]):
            ct = response.headers.get("content-type", "")

            if "application/json" in ct:
                captured_api_data = await response.json()

    except:
        pass


# =========================
# FALLBACK HTML PARSER (ONLY IF API FAILS)
# =========================
def parse_html(html):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    return {
        "tables": soup.find_all("table"),
        "text": soup.get_text(" ", strip=True)
    }


# =========================
# FORMAT FROM API (PRIMARY)
# =========================
def format_from_api(api):

    result = {
        "score": {},
        "batters": [],
        "bowlers": [],
        "fall_of_wickets": [],
        "extras": {},
        "yet_to_bat": []
    }

    if not isinstance(api, dict):
        return result

    # --------------------
    # SCORE
    # --------------------
    try:
        score = api.get("score", {})
        result["score"] = {
            "runs": to_int(score.get("runs")),
            "wickets": to_int(score.get("wickets")),
            "overs": to_float(score.get("overs"))
        }
    except:
        pass

    # --------------------
    # BATTERS (multi-format safe)
    # --------------------
    for b in api.get("batters", []):
        result["batters"].append({
            "name": b.get("name", ""),
            "runs": to_int(b.get("runs")),
            "balls": to_int(b.get("balls")),
            "fours": to_int(b.get("fours")),
            "sixes": to_int(b.get("sixes")),
            "strike_rate": to_float(b.get("strike_rate"))
        })

    # --------------------
    # BOWLERS
    # --------------------
    for b in api.get("bowlers", []):
        result["bowlers"].append({
            "name": b.get("name", ""),
            "overs": to_float(b.get("overs")),
            "maidens": to_int(b.get("maidens")),
            "runs": to_int(b.get("runs")),
            "wickets": to_int(b.get("wickets")),
            "economy": to_float(b.get("economy"))
        })

    # --------------------
    # FOW
    # --------------------
    for w in api.get("fall_of_wickets", []):
        result["fall_of_wickets"].append({
            "player": w.get("player", ""),
            "score": w.get("score", ""),
            "over": to_float(w.get("over"))
        })

    # --------------------
    # EXTRAS
    # --------------------
    result["extras"] = api.get("extras", {}) or {}

    # --------------------
    # YET TO BAT
    # --------------------
    result["yet_to_bat"] = api.get("yet_to_bat", []) or []

    return result


# =========================
# MAIN FORMATTER
# =========================
def format_scorecard(html):

    global captured_api_data

    # 🔥 PRIORITY 1: USE API DATA
    if captured_api_data:
        return format_from_api(captured_api_data)

    # 🔥 FALLBACK (HTML ONLY IF API FAILS)
    return {
        "score": {},
        "batters": [],
        "bowlers": [],
        "fall_of_wickets": [],
        "extras": {},
        "yet_to_bat": []
    }


# =========================
# MAIN LOADER
# =========================
async def load_scorecard(url):
    html = await get_page_html(url)
    return format_scorecard(html)