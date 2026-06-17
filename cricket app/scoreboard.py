import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import json


URL = "https://crex.com/cricket-live-score/aus-vs-ban-1st-t20-australia-tour-of-bangladesh-2026-match-updates-11PR/match-scorecard"


async def get_page_html(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True
        )

        page = await browser.new_page()

        await page.goto(
            url,
            wait_until="networkidle",
            timeout=120000
        )

        # wait for scorecard tab content
        await page.wait_for_timeout(5000)

        html = await page.content()

        await browser.close()

        return html


def parse_scorecard(html: str):

    soup = BeautifulSoup(html, "html.parser")

    data = {
        "teams": [],
        "innings": []
    }

    # ==========================
    # TEAM SCORE BLOCKS
    # ==========================
    score_blocks = soup.select(
        ".team-score, .score-card, .score-over"
    )

    for block in score_blocks:
        txt = block.get_text(" ", strip=True)

        if txt:
            data["teams"].append(txt)

    # ==========================
    # TABLES
    # ==========================
    tables = soup.find_all("table")

    for table in tables:

        headers = [
            th.get_text(" ", strip=True)
            for th in table.find_all("th")
        ]

        rows = []

        for tr in table.find_all("tr"):

            cols = [
                td.get_text(" ", strip=True)
                for td in tr.find_all("td")
            ]

            if cols:
                rows.append(cols)

        if headers or rows:
            data["innings"].append({
                "headers": headers,
                "rows": rows
            })

    return data


import re


def safe_int(v, default=0):
    try:
        return int(v)
    except:
        return default


def safe_float(v, default=0.0):
    try:
        return float(v)
    except:
        return default


def format_scorecard(scorecard):

    result = {
        "score": {},
        "batters": [],
        "bowlers": [],
        "fall_of_wickets": [],
        "extras": {},
        "yet_to_bat": []
    }

    # =========================
    # SCORE
    # =========================
    for item in scorecard.get("teams", []):

        m = re.search(r"(\d+)-(\d+)\s*\(?([\d.]+)\)?", item)

        if m:
            result["score"] = {
                "runs": safe_int(m.group(1)),
                "wickets": safe_int(m.group(2)),
                "overs": safe_float(m.group(3))
            }
            break

    # =========================
    # TABLE DETECTION
    # =========================
    for table in scorecard.get("innings", []):

        headers = [h.lower() for h in table.get("headers", [])]
        rows = table.get("rows", [])

        # =====================
        # BATTERS
        # =====================
        if (
            "batter" in headers
            or ("r" in headers and "b" in headers and "sr" in headers)
        ):

            for row in rows:

                if len(row) < 6:
                    continue

                result["batters"].append({
                    "name": row[0],
                    "runs": safe_int(row[1]),
                    "balls": safe_int(row[2]),
                    "fours": safe_int(row[3]),
                    "sixes": safe_int(row[4]),
                    "strike_rate": safe_float(row[5])
                })

        # =====================
        # BOWLERS
        # =====================
        elif (
            "bowler" in headers
            or ("o" in headers and "w" in headers)
        ):

            for row in rows:

                if len(row) < 6:
                    continue

                result["bowlers"].append({
                    "name": row[0],
                    "overs": safe_float(row[1]),
                    "maidens": safe_int(row[2]),
                    "runs": safe_int(row[3]),
                    "wickets": safe_int(row[4]),
                    "economy": safe_float(row[5])
                })

        # =====================
        # FALL OF WICKETS
        # =====================
        elif (
            "score" in headers
            and "overs" in headers
        ):

            for row in rows:

                if len(row) < 3:
                    continue

                result["fall_of_wickets"].append({
                    "player": row[0],
                    "score": row[1],
                    "over": safe_float(row[2])
                })

    # =========================
    # EXTRAS
    # =========================
    for item in scorecard.get("teams", []):

        extras_match = re.search(
            r"Extras:\s*(\d+)",
            item,
            re.IGNORECASE
        )

        if extras_match:

            result["extras"]["total"] = safe_int(
                extras_match.group(1)
            )

            breakdown = re.search(
                r"b\s*(\d+).*?lb\s*(\d+).*?w\s*(\d+).*?nb\s*(\d+).*?p\s*(\d+)",
                item,
                re.IGNORECASE
            )

            if breakdown:

                result["extras"].update({
                    "byes": safe_int(breakdown.group(1)),
                    "leg_byes": safe_int(breakdown.group(2)),
                    "wides": safe_int(breakdown.group(3)),
                    "no_balls": safe_int(breakdown.group(4)),
                    "penalty": safe_int(breakdown.group(5))
                })

    # =========================
    # YET TO BAT
    # =========================
    for item in scorecard.get("teams", []):

        if "yet to bat" in item.lower():

            text = re.sub(
                r"Yet to bat",
                "",
                item,
                flags=re.IGNORECASE
            )

            players = re.findall(
                r"([A-Za-z.\s]+?)\s+Avg:",
                text
            )

            result["yet_to_bat"] = [
                p.strip()
                for p in players
                if p.strip()
            ]

            break

    return result



async def load_data(url):

    html = await get_page_html(url+'/match-scorecard')

    scorecard = parse_scorecard(html)
    print(url)
    print(
        json.dumps(
            scorecard,
            indent=2,
            ensure_ascii=False
        ))
    return format_scorecard(scorecard)
    """print(
        json.dumps(
            scorecard,
            indent=2,
            ensure_ascii=False
        )
        
    )"""
"""
    print(format_scorecard(scorecard))

if __name__ == "__main__":
    asyncio.run(main())"""