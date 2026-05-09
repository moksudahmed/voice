from playwright.async_api import async_playwright
import asyncio

async def scraper_loop():

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )

        page = await browser.new_page()

        await page.goto(URL)

        while True:

            try:

                await page.reload(
                    wait_until="domcontentloaded"
                )

                score = await page.locator(
                    ".live-score"
                ).inner_text()

                overs = await page.locator(
                    ".overs"
                ).inner_text()

                STATE["data"]["score"] = score
                STATE["data"]["overs"] = overs

                STATE["version"] += 1

            except Exception as e:
                print(e)

            await asyncio.sleep(0.15)