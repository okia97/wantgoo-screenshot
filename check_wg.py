import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://www.wantgoo.com/index/0000')
        await asyncio.sleep(5)
        html = await page.content()
        with open('wg.html', 'w', encoding='utf-8') as f:
            f.write(html)
        await browser.close()

asyncio.run(main())
