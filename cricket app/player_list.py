from playwright.async_api import async_playwright
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
import asyncio

app = FastAPI()

# =========================================================
# SCRAPER
# =========================================================

async def scrape_playing_xi(page):

    result = {
        "team_a": {
            "name": "",
            "players": []
        },
        "team_b": {
            "name": "",
            "players": []
        }
    }

    try:

        await page.wait_for_selector(
            "app-playingxi-card",
            timeout=20000
        )

        team_buttons = page.locator(
            "button.playingxi-button"
        )

        total_teams = await team_buttons.count()

        if total_teams < 2:
            return result

        # =====================================================
        # EXTRACT PLAYERS
        # =====================================================

        async def extract_players():

            players = []

            rows = page.locator(
                "div.playingxi-card-row"
            )

            count = await rows.count()

            for i in range(count):

                row = rows.nth(i)

                try:

                    full_name = await row.locator(
                        "a"
                    ).get_attribute("title")

                    short_name = await row.locator(
                        ".p-name"
                    ).inner_text()

                    # ROLE
                    role = ""

                    role_locator = row.locator(
                        ".bat-ball-type div"
                    )

                    if await role_locator.count() > 0:
                        role = await role_locator.inner_text()

                    # TAG
                    tag = ""

                    flex_div = row.locator(".flex")

                    texts = await flex_div.locator(
                        "div"
                    ).all_inner_texts()

                    if len(texts) > 1:
                        tag = texts[1].strip()

                    # IMAGE
                    image = ""

                    img_locator = row.locator(
                        "img[title]"
                    ).first

                    if await img_locator.count() > 0:

                        image = await img_locator.get_attribute(
                            "src"
                        )

                    # PROFILE
                    profile = await row.locator(
                        "a"
                    ).get_attribute("href")

                    players.append({
                        "full_name": full_name,
                        "short_name": short_name.strip(),
                        "role": role.strip(),
                        "tag": tag,
                        "image": image,
                        "profile": profile
                    })

                except Exception as e:
                    print("PLAYER ERROR:", e)

            return players

        # =====================================================
        # TEAM A
        # =====================================================

        team_a_btn = team_buttons.nth(0)

        result["team_a"]["name"] = (
            await team_a_btn.inner_text()
        ).strip()

        await team_a_btn.click()

        await page.wait_for_timeout(1200)

        result["team_a"]["players"] = (
            await extract_players()
        )

        # =====================================================
        # TEAM B
        # =====================================================

        team_b_btn = team_buttons.nth(1)

        result["team_b"]["name"] = (
            await team_b_btn.inner_text()
        ).strip()

        await team_b_btn.click()

        await page.wait_for_timeout(1200)

        result["team_b"]["players"] = (
            await extract_players()
        )

        return result

    except Exception as e:

        print("SCRAPE ERROR:", e)

        return result


# =========================================================
# FETCH PLAYERS
# =========================================================

async def get_playing_xi(url):

    #url = "https://crex.com/cricket-live-score/kkr-vs-rcb-57th-match-indian-premier-league-2026-match-updates-1192"

    url = url.rstrip("/") + "/match-details"

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )

        page = await browser.new_page()

        await page.goto(
            url,
            wait_until="networkidle",
            timeout=60000
        )

        playing_xi = await scrape_playing_xi(page)

        await browser.close()

        return playing_xi


# =========================================================
# HTML GENERATOR
# =========================================================

def generate_team_html(team, class_name):

    players_html = ""

    for player in team["players"]:

        players_html += f"""
        <div class="player-card">

            <img
                src="{player['image']}"
                class="player-img"
            >

            <div class="player-info">

                <div class="player-name">
                    {player['full_name']}
                    <span class="tag">
                        {player['tag']}
                    </span>
                </div>

                <div class="player-role">
                    {player['role']}
                </div>

            </div>

        </div>
        """

    return f"""
    <div class="team-container">

        <div class="team-header {class_name}">
            {team['name']}
        </div>

        <div class="players-grid">
            {players_html}
        </div>

    </div>
    """

