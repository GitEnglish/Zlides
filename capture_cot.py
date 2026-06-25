import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("Navigating to http://localhost:5173")
        await page.goto("http://localhost:5173")

        print("Waiting for Generate button...")
        await page.wait_for_selector("button:has-text('Generate')")

        print("Typing into textarea...")
        await page.fill("textarea", "Make me some slides about dogs")

        # Click the Generate button
        print("Clicking Generate...")
        await page.click("button:has-text('Generate')")

        # Wait for a bit so the stream can start and thought/tool pills can appear
        print("Waiting for 4 seconds to capture active stream...")
        await asyncio.sleep(4)

        # Take an explicit screenshot of the whole page
        await page.screenshot(path="active_stream_full.png", full_page=True)
        print("Screenshot saved to active_stream_full.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
