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

async def get_playing_xi():

    url = "https://crex.com/cricket-live-score/kkr-vs-rcb-57th-match-indian-premier-league-2026-match-updates-1192"

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


# =========================================================
# HTML PAGE
# =========================================================

@app.get("/", response_class=HTMLResponse)
async def home():

    data = await get_playing_xi()

    team_a_html = generate_team_html(
        data["team_a"],
        "team-a"
    )

    team_b_html = generate_team_html(
        data["team_b"],
        "team-b"
    )

    html = f"""
    <!DOCTYPE html>
    <html lang="en">

    <head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Playing XI</title>

    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">

    <style>

    *{{
        margin:0;
        padding:0;
        box-sizing:border-box;
    }}

    body{{
        background:#050505;
        color:#fff;
        font-family:'Poppins',sans-serif;
        padding:30px;
    }}

    .main-title{{
        text-align:center;
        font-size:60px;
        font-weight:900;
        margin-bottom:40px;

        background:linear-gradient(
            90deg,
            #fff,
            #ffd84d,
            #ff9800
        );

        -webkit-background-clip:text;
        -webkit-text-fill-color:transparent;
    }}

    .teams{{
        display:grid;
        grid-template-columns:1fr 1fr;
        gap:30px;
    }}

    .team-container{{
        background:
        linear-gradient(
            135deg,
            rgba(255,255,255,.08),
            rgba(255,255,255,.03)
        );

        border:1px solid rgba(255,255,255,.08);

        border-radius:30px;

        overflow:hidden;
    }}

    .team-header{{
        padding:22px;
        font-size:32px;
        font-weight:900;
        text-align:center;
    }}

    .team-a{{
        background:
        linear-gradient(
            135deg,
            #ff003c,
            #ff9800
        );
    }}

    .team-b{{
        background:
        linear-gradient(
            135deg,
            #6a00ff,
            #c400ff
        );
    }}

    .players-grid{{
        padding:20px;

        display:grid;
        grid-template-columns:1fr 1fr;
        gap:18px;
    }}

    .player-card{{
        display:flex;
        align-items:center;
        gap:15px;

        padding:16px;

        border-radius:20px;

        background:
        linear-gradient(
            135deg,
            rgba(255,255,255,.08),
            rgba(255,255,255,.02)
        );

        transition:.3s;
    }}

    .player-card:hover{{
        transform:translateY(-5px);
    }}

    .player-img{{
        width:80px;
        height:80px;

        border-radius:50%;
        object-fit:cover;

        border:3px solid rgba(255,255,255,.15);
    }}

    .player-info{{
        flex:1;
    }}

    .player-name{{
        font-size:20px;
        font-weight:800;
        line-height:1.3;
    }}

    .tag{{
        color:#ffd84d;
        margin-left:6px;
    }}

    .player-role{{
        margin-top:8px;

        display:inline-block;

        padding:5px 12px;

        border-radius:30px;

        background:rgba(0,229,255,.12);

        border:1px solid rgba(0,229,255,.25);

        color:#00e5ff;

        font-size:12px;
        font-weight:700;
    }}

    @media(max-width:1200px){{
        .teams{{
            grid-template-columns:1fr;
        }}
    }}

    @media(max-width:700px){{
        .players-grid{{
            grid-template-columns:1fr;
        }}

        .main-title{{
            font-size:38px;
        }}
    }}

    </style>

    </head>

    <body>

        <div class="main-title">
            PLAYING XI
        </div>

        <div class="teams">

            {team_a_html}

            {team_b_html}

        </div>

    </body>

    </html>
    """

    return HTMLResponse(content=html)


# =========================================================
# JSON API
# =========================================================

@app.get("/api/players")
async def api_players():

    data = await get_playing_xi()

    return JSONResponse(content=data)


# =========================================================
# RUN SERVER
# =========================================================

if __name__ == "__main__":

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )