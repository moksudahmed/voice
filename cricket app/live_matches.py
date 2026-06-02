from playwright.async_api import async_playwright
from pydantic import BaseModel

# =========================
# REQUEST MODEL
# =========================
class UrlRequest(BaseModel):
    url: str | None = None

async def get_live_matches2():
    matches = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        CREX_URL = "https://crex.com/cricket-live-score"
        
        await page.goto(CREX_URL, timeout=60000)
        await page.wait_for_timeout(5000)  # allow JS load

        # match cards (CREX structure)
        #cards = await page.locator(".match-card, .match-box, .scorecard, a").all()
        cards = await page.locator("app-live-matches .live-card").all()
        #print(cards)
        for card in cards:
            try:
                text = await card.inner_text()

                # filter only live matches
                if "LIVE" in text.upper() or "STUMPS" in text.upper():

                    teams = await card.locator("text=/vs/i").all_inner_texts()

                    link = await card.get_attribute("href")
                    if link and link.startswith("/"):
                        link = "https://crex.com" + link

                    matches.append({
                        "text": text.strip(),
                        "url": link
                    })

            except:
                continue

        await browser.close()

    return matches

async def get_live_matches():
    matches = []

    CREX_URL = "https://crex.com/cricket-live-score"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(CREX_URL, timeout=60000)
        await page.wait_for_timeout(6000)  # wait Angular render

        # =========================
        # LIVE MATCH CARDS
        # =========================
        cards = await page.locator("div.live-card").all()

        for card in cards:
            try:
                # =========================
                # CHECK LIVE STATUS
                # =========================
                live_tag = await card.locator(".liveTag").all_inner_texts()
                if not any("live" in t.lower() for t in live_tag):
                    continue

                # =========================
                # SERIES NAME (TOP)
                # =========================
                series = await card.locator("h2.snameTag").first.inner_text()
                series = series.strip() if series else "Live Match"

                # =========================
                # MATCH URL (MAIN LINK)
                # =========================
                match_link_el = card.locator(
                    "a[href*='cricket-live-score'], a[href*='match-updates']"
                ).last

                href = await match_link_el.get_attribute("href")

                if href and href.startswith("/"):
                    href = "https://crex.com" + href

                # =========================
                # MATCH TITLE / INFO
                # =========================
                match_info = await card.locator("h3.match-number").first.inner_text()
                match_info = match_info.strip() if match_info else ""

                # =========================
                # COMMENT (IMPORTANT INFO)
                # =========================
                comment = await card.locator(".comment").first.inner_text()
                comment = comment.strip() if comment else ""

                # =========================
                # TEAMS + SCORES
                # =========================
                teams = await card.locator(".team-name").all_inner_texts()
                scores = await card.locator(".team-score").all_inner_texts()
                overs = await card.locator(".match-over").all_inner_texts()

                team_info = ""
                if len(teams) >= 2:
                    team_info = f"{teams[0]} vs {teams[1]}"

                score_info = ""
                if scores:
                    score_info = " | ".join([s.strip() for s in scores if s.strip()])

                over_info = ""
                if overs:
                    over_info = "Overs: " + " | ".join(overs)

                # =========================
                # FINAL FORMAT
                # =========================
                text = "\n".join(filter(None, [
                    series,
                    match_info,
                    team_info,
                    score_info,
                    over_info,
                    comment
                ]))
                # =========================
                # STATE SAVE (FIXED)
                # =========================
                MATCH_INFO = {
                    "series": series,
                    "match_info": match_info,
                    "team_info": team_info,
                    "score_info": score_info,
                    "over_info": over_info,
                    "comment": comment,
                    "url": href
                }
                matches.append({
                    "text": text,
                    "url": href
                })

            except Exception as e:
                print("❌ CARD ERROR:", e)
                continue

        await browser.close()

    return matches

