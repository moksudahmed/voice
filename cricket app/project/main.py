from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

import asyncio
import re
import time

# =========================================================
# APP
# =========================================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# STATE
# =========================================================

STATE = {
    "url": "",
    "connected": False,
    "data": {}
}

clients = set()

# =========================================================
# CLEANER
# =========================================================

def clean(t):
    return re.sub(r"\s+", " ", t).strip() if t else ""

# =========================================================
# FAST PARSER (OPTIMIZED FOR CREX + ANGULAR)
# =========================================================
def parse_score(text):
    match = re.search(r'(\d+)-(\d)(\d+)\.([0-5])', text)
    if not match:
        return None

    runs = int(match.group(1))
    wickets = int(match.group(2))
    over = int(match.group(3))
    ball = int(match.group(4))

    return runs, wickets, over, ball

def get_over_before_crr(text):
    lines = text.splitlines()
    try:
        for i, item in enumerate(lines):
            if "CRR" in item:
                # return previous non-empty value
                j = i - 1
                while j >= 0:
                    val = lines[j].strip()
                    if val:   # skip empty strings
                        return val
                    j -= 1
    except Exception as e:
        print("Error:", e)

    return None
async def extract_result_and_ball(page):

    try:

        # =========================
        # RESULT BOX (IMPORTANT FIX)
        # =========================
        result = await page.locator(
            ".result-box span"
        ).all_text_contents()

        result = [r.strip() for r in result if r.strip()]

        # =========================
        # BALL VALUE (4 / 6 / WICKET)
        # =========================
        ball_event = await page.locator(
            ".result-box"
        ).first.get_attribute("class")

        ball_value = None

        # fallback: read actual number inside span
        try:
            ball_value = await page.locator(
                ".result-box span"
            ).first.text_content()
            ball_value = ball_value.strip()
        except:
            pass

        return {
            "result_text": result[0] if result else "",
            "ball": ball_value,
            "type": ball_event
        }

    except Exception as e:
        print("RESULT PARSE ERROR:", e)
        return {
            "result_text": "",
            "ball": "",
            "type": ""
        }
def parse_all(text):

    data = {
        "team_a": "TEAM A",
        "team_b": "TEAM B",

        "score": "0/0",
        "overs": "0.0",
        "crr": "0.00",

        "status": "",
        "commentary": "",

        "bowler": "",
        "bowler_fig": "",

        "striker": "",
        "non_striker": "",

        "partnership": "",
        "last_wicket": "",

        "updated": int(time.time())
    }

    # =====================================================
    # SCORE (FIXED FOR 203/7, NOT 203/741 BUG)
    # =====================================================
    #score = re.search(r"(\d+)\s*[-/]\s*(\d{1,2})", text)
    
    score = parse_score(text)
    if score:
        data["score"] = score
    
    
    # =====================================================
    # OVERS
    # =====================================================
    """overs = re.search(r"(\d+\.\d+)\s*Overs|\bOvers\s*[:\-]?\s*(\d+\.\d+)", text, re.I)
    if overs:
        data["score"] = overs.group(1) or overs.group(2)
    print(overs)"""

    # =====================================================
    # CRR
    # =====================================================
    crr = re.search(r"CRR\s*:?\s*([\d\.]+)", text)
    if crr:
        data["crr"] = crr.group(1)
        

    # =====================================================
    # TEAMS (SAFE)
    # =====================================================
    teams = re.search(r"([A-Z][A-Za-z\s\-]+)\s+vs\s+([A-Z][A-Za-z\s\-]+)", text)
    if teams:
        data["team_a"] = clean(teams.group(1))
        data["team_b"] = clean(teams.group(2))
        
    # =====================================================
    # STATUS (LIVE / BREAK / COMMENT)
    # =====================================================
    """for line in text.split("\n"):
        if any(x in line.lower() for x in ["live", "innings", "break", "opt to"]):
            data["status"] = clean(line)            
            break"""
    last_status_message = get_over_before_crr(text)
    #print(last_status_message)
    # =====================================================
    # BOWLER
    # =====================================================
    """bowler = re.search(r"([A-Z][A-Za-z\s\.]+)\s+(\d+-\d+)\s*\(([\d\.]+)\)", text)
    if bowler:
        data["bowler"] = clean(bowler.group(1))
        data["bowler_fig"] = f"{bowler.group(2)} ({bowler.group(3)})"""
        
    # =====================================================
    # BATSMEN
    # =====================================================
    bats = re.findall(r"([A-Z][A-Za-z\s\.]+)\s+(\d+)\s*\((\d+)\)", text)

    if len(bats) > 0:
        data["striker"] = clean(bats[0][0])

    if len(bats) > 1:
        data["non_striker"] = clean(bats[1][0])

    # =====================================================
    # PARTNERSHIP
    # =====================================================
    p = re.search(r"P'ship\s*:?\s*(\d+\(\d+\))", text)
    if p:
        data["partnership"] = p.group(1)

    # =====================================================
    # LAST WICKET
    # =====================================================
    """lw = re.search(r"Last Wkt\s*:\s*(.*)", text)
    if lw:
        data["last_wicket"] = clean(lw.group(1))"""
    print(data)
    return data

# =========================================================
# SCRAPER (ULTRA LOW LATENCY VERSION)
# =========================================================

async def scraper2():

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=True
    )

    page = await browser.new_page()

    last_state = None

    while True:

        try:

            if not STATE["url"]:
                await asyncio.sleep(0.3)
                continue

            # =====================================================
            # FIRST LOAD ONLY
            # =====================================================
            if not STATE["connected"]:

                await page.goto(
                    STATE["url"],
                    wait_until="domcontentloaded"
                )

                await page.wait_for_timeout(2500)

                # 🔥 inject mutation tracker (NO RELOAD EVER)
                await page.evaluate("""
                    window.__dirty = true;

                    const obs = new MutationObserver(() => {
                        window.__dirty = true;
                    });

                    obs.observe(document.body, {
                        childList: true,
                        subtree: true,
                        characterData: true
                    });
                """)

                STATE["connected"] = True

            # =====================================================
            # WAIT FOR DOM CHANGE ONLY
            # =====================================================
            changed = await page.evaluate("window.__dirty")

            if not changed:
                await asyncio.sleep(0.2)
                continue

            await page.evaluate("window.__dirty = false")

            # =====================================================
            # FAST SNAPSHOT (NO LOCATORS)
            # =====================================================
            html = await page.content()
            text = await page.inner_text("body")
            #print(text)
            parsed = parse_all(html + "\n" + text)
            # =====================================================
            # SEND ONLY IF CHANGED
            # =====================================================
            if parsed != last_state:
                last_state = parsed
                STATE["data"] = parsed
                
                dead = []

                for ws in list(clients):
                    try:
                        await ws.send_json(parsed)
                    except:
                        dead.append(ws)

                for d in dead:
                    clients.remove(d)

                print("📡 UPDATE:", parsed["score"], parsed["overs"])

            # =====================================================
            # ULTRA FAST LOOP
            # =====================================================
            await asyncio.sleep(0.15)

        except Exception as e:
            print("❌ SCRAPER ERROR:", e)
            STATE["connected"] = False
            await asyncio.sleep(2)
async def scraper():

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()

    last_state = None

    while True:

        try:

            if not STATE["url"]:
                await asyncio.sleep(0.15)
                continue

            # =====================================================
            # FIRST LOAD ONLY
            # =====================================================
            if not STATE["connected"]:

                await page.goto(
                    STATE["url"],
                    wait_until="domcontentloaded"
                )

                await page.wait_for_timeout(2000)

                # 🔥 fast mutation flag
                await page.evaluate("""
                    window.__dirty = true;

                    const obs = new MutationObserver(() => {
                        window.__dirty = true;
                    });

                    obs.observe(document.body, {
                        childList: true,
                        subtree: true,
                        characterData: true
                    });
                """)

                STATE["connected"] = True

            # =====================================================
            # SKIP IF NO CHANGE
            # =====================================================
            if not await page.evaluate("window.__dirty"):
                await asyncio.sleep(0.12)
                continue

            await page.evaluate("window.__dirty = false")

            # =====================================================
            # 🔥 FULL HYBRID DOM + TEXT ENGINE
            # =====================================================
            # =====================================================
            # 🔥 FULL HYBRID DOM + TEXT ENGINE (REWRITTEN)
            # =====================================================

            parsed = await page.evaluate("""
            () => {

                // =================================================
                // HELPERS
                // =================================================

                const clean = (t) =>
                    (t || "")
                        .replace(/\\s+/g, " ")
                        .trim();

                const safeText = (selector) => {

                    const el = document.querySelector(selector);

                    return el
                        ? clean(el.innerText)
                        : "";
                };

                const safeImg = (selector) => {

                    const el = document.querySelector(selector);

                    return el
                        ? el.src
                        : "";
                };

                // =================================================
                // DATA OBJECT
                // =================================================

                const data = {

                    // MATCH
                    team_a: "",
                    team_b: "",

                    score: "",
                    overs: "",
                    crr: "",

                    status: "",
                    commentary: "",

                    // BOWLER
                    bowler: "",
                    bowler_fig: "",
                    bowler_img: "",

                    // STRIKER
                    striker: "",
                    striker_runs: "",
                    striker_balls: "",
                    striker_full: "",
                    striker_img: "",

                    // NON STRIKER
                    non_striker: "",
                    non_striker_runs: "",
                    non_striker_balls: "",
                    non_striker_full: "",
                    non_striker_img: "",

                    // EXTRA
                    partnership: "",
                    last_wicket: "",

                    // TIMELINE
                    overs_timeline: [],

                    // RESULT
                    result_boxes: [],

                    // PLAYERS
                    live_players: {
                        batsmen: [],
                        bowler: null
                    },

                    updated: Date.now()
                };

                // =================================================
                // BODY TEXT
                // =================================================

                const bodyText =
                    clean(document.body.innerText);

                // =================================================
                // TEAM NAMES
                // =================================================

                const teamMatch =
                    bodyText.match(
                        /([A-Za-z\\s\\-]+)\\s+vs\\s+([A-Za-z\\s\\-]+)/i
                    );

                if (teamMatch) {

                    data.team_a =
                        clean(teamMatch[1]);

                    data.team_b =
                        clean(teamMatch[2]);
                }

                // =================================================
                // SCORE + OVERS
                // Example:
                // 147-2 (14.2)
                // 147/2 14.2
                // =================================================

                const scoreOverMatch =
                    bodyText.match(
                        /(\\d{1,3})\\s*[-/]\\s*(\\d{1,2})\\s*\\(?\\s*(\\d{1,2}\\.\\d)\\s*\\)?/
                    );

                if (scoreOverMatch) {

                    const runs =
                        scoreOverMatch[1];

                    const wickets =
                        scoreOverMatch[2];

                    const overs =
                        scoreOverMatch[3];

                    data.score =
                        `${runs}/${wickets}`;

                    data.overs =
                        overs;
                }

                // =================================================
                // CRR
                // =================================================

                const crrMatch =
                    bodyText.match(
                        /CRR\\s*:?\\s*(\\d+\\.\\d+)/i
                    );

                if (crrMatch) {

                    data.crr =
                        crrMatch[1];
                }

                // =================================================
                // STATUS
                // =================================================

                const statusMatch =
                    bodyText.match(
                        /(LIVE|Match Info|Stumps|Innings Break|Opt to Bat|Won by.*)/i
                    );

                if (statusMatch) {

                    data.status =
                        clean(statusMatch[1]);
                }

                // =================================================
                // COMMENTARY
                // =================================================

                const commentaryEl =
                    document.querySelector(
                        ".commentary-text, .live-commentary, .commentary"
                    );

                if (commentaryEl) {

                    data.commentary =
                        clean(commentaryEl.innerText);
                }

                // =================================================
                // PARTNERSHIP
                // =================================================

                const partnershipMatch =
                    bodyText.match(
                        /(\\d+)\\((\\d+)\\)/
                    );

                if (partnershipMatch) {

                    data.partnership =
                        `${partnershipMatch[1]}(${partnershipMatch[2]})`;
                }

                // =================================================
                // LAST WICKET
                // =================================================

                const wicketMatch =
                    bodyText.match(
                        /Last Wkt\\s*:??\\s*(.*)/i
                    );

                if (wicketMatch) {

                    data.last_wicket =
                        clean(wicketMatch[1]);
                }

                // =================================================
                // RESULT BOXES
                // =================================================

                document
                    .querySelectorAll(".result-box")
                    .forEach(el => {

                        const txt =
                            clean(el.innerText);

                        if (txt) {

                            data.result_boxes.push(txt);
                        }
                    });

                // =================================================
                // LIVE PLAYER SECTION
                // =================================================

                const playerSection =
                    document.querySelector(
                        ".player-profile"
                    );

                if (playerSection) {

                    // =============================================
                    // BATSMEN
                    // =============================================

                    const batsmenCards =
                        playerSection.querySelectorAll(
                            ".batsmen-partnership"
                        );

                    batsmenCards.forEach(card => {

                        // Skip bowler card
                        if (
                            card.querySelector(
                                ".batsmen-score.bowler"
                            )
                        ) {
                            return;
                        }

                        const img =
                            card.querySelector(
                                ".batsmen-image img"
                            );

                        const name =
                            card.querySelector(
                                ".batsmen-name p"
                            );

                        const scorePs =
                            card.querySelectorAll(
                                ".batsmen-score p"
                            );

                        let runs = "";
                        let balls = "";

                        if (scorePs.length >= 2) {

                            runs =
                                clean(scorePs[0].innerText);

                            balls =
                                clean(scorePs[1].innerText)
                                    .replace(/[()]/g, "");
                        }

                        data.live_players.batsmen.push({

                            name: name
                                ? clean(name.innerText)
                                : "",

                            runs: runs,

                            balls: balls,

                            image: img
                                ? img.src
                                : ""
                        });
                    });

                    // =============================================
                    // BOWLER
                    // =============================================

                    const bowlerCard =
                        playerSection.querySelector(
                            ".batsmen-partnership:has(.batsmen-score.bowler)"
                        );

                    if (bowlerCard) {

                        const bowlerImg =
                            bowlerCard.querySelector(
                                ".batsmen-image img"
                            );

                        const bowlerName =
                            bowlerCard.querySelector(
                                ".batsmen-name p"
                            );

                        const figures =
                            bowlerCard.querySelectorAll(
                                ".batsmen-score.bowler p"
                            );

                        let fig = "";

                        if (figures.length >= 2) {

                            fig =
                                clean(figures[0].innerText) +
                                " " +
                                clean(figures[1].innerText);
                        }

                        data.live_players.bowler = {

                            name: bowlerName
                                ? clean(bowlerName.innerText)
                                : "",

                            figures: fig,

                            image: bowlerImg
                                ? bowlerImg.src
                                : ""
                        };
                    }
                }

                // =================================================
                // STRIKER
                // =================================================

                if (
                    data.live_players.batsmen.length >= 1
                ) {

                    const s =
                        data.live_players.batsmen[0];

                    data.striker =
                        s.name;

                    data.striker_runs =
                        s.runs;

                    data.striker_balls =
                        s.balls;

                    data.striker_full =
                        `${s.name} ${s.runs} (${s.balls})`;

                    data.striker_img =
                        s.image;
                }

                // =================================================
                // NON STRIKER
                // =================================================

                if (
                    data.live_players.batsmen.length >= 2
                ) {

                    const ns =
                        data.live_players.batsmen[1];

                    data.non_striker =
                        ns.name;

                    data.non_striker_runs =
                        ns.runs;

                    data.non_striker_balls =
                        ns.balls;

                    data.non_striker_full =
                        `${ns.name} ${ns.runs} (${ns.balls})`;

                    data.non_striker_img =
                        ns.image;
                }

                // =================================================
                // BOWLER
                // =================================================

                if (data.live_players.bowler) {

                    data.bowler =
                        data.live_players.bowler.name;

                    data.bowler_fig =
                        data.live_players.bowler.figures;

                    data.bowler_img =
                        data.live_players.bowler.image;
                }

                // =================================================
                // OVERS TIMELINE
                // =================================================

                document
                    .querySelectorAll(".overs-slide")
                    .forEach(overEl => {

                        const overData = {

                            over: "",
                            balls: [],
                            total: ""
                        };

                        // OVER TITLE

                        const overTitle =
                            overEl.querySelector("span");

                        if (overTitle) {

                            overData.over =
                                clean(overTitle.innerText);
                        }

                        // BALLS

                        overEl
                            .querySelectorAll(".over-ball")
                            .forEach(ball => {

                                const val =
                                    clean(ball.innerText);

                                if (val) {

                                    overData.balls.push(val);
                                }
                            });

                        // TOTAL

                        const total =
                            overEl.querySelector(".total");

                        if (total) {

                            overData.total =
                                clean(
                                    total.innerText.replace("=", "")
                                );
                        }

                        data.overs_timeline.push(overData);
                    });

                // =================================================
                // RETURN
                // =================================================

                return data;
            }
            """)
            # =====================================================
            # SEND ONLY IF CHANGED (FAST HASH STYLE OPTIONAL)
            # =====================================================
            if parsed != last_state:
                last_state = parsed
                STATE["data"] = parsed

                dead = []

                for ws in list(clients):
                    try:
                        await ws.send_json(parsed)
                    except:
                        dead.append(ws)

                for d in dead:
                    clients.remove(d)

                print("📡 UPDATE:", parsed["result_boxes"])

            await asyncio.sleep(0.12)

        except Exception as e:
            print("❌ SCRAPER ERROR:", e)
            STATE["connected"] = False
            await asyncio.sleep(2)
# =========================================================
# STARTUP
# =========================================================

@app.on_event("startup")
async def startup():
    asyncio.create_task(scraper())

# =========================================================
# ROUTES
# =========================================================

@app.get("/")
def home():
    return FileResponse("templates/home.html")

@app.get("/overlay")
def overlay():
    return FileResponse("templates/overlay.html")

@app.post("/set-url")
async def set_url(payload: dict):

    STATE["url"] = payload.get("url", "")
    STATE["connected"] = False

    return {"ok": True}

# =========================================================
# WEBSOCKET
# =========================================================

@app.websocket("/ws")
async def ws(websocket: WebSocket):

    await websocket.accept()
    clients.add(websocket)

    print("🔌 CLIENT CONNECTED")

    try:
        while True:
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        clients.remove(websocket)
        print("❌ CLIENT DISCONNECTED")