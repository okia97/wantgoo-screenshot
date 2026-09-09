#!/usr/bin/env python3
"""
玩股網 國際指數自動截圖程式
每週日 12:00 由 macOS launchd 自動執行
截取印度/泰國/印尼/澳洲指數的日線、周線、月線並依日期儲存
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
try:
    from playwright_stealth import stealth_async
except ImportError:
    stealth_async = None

# ── 設定 ──────────────────────────────────────────────────────────────────────

# 各指數設定：(識別碼, 名稱, 頁面 URL) 分類
MARKET_GROUPS = {
    "亞洲": [
        ("twii",   "台灣加權",      "https://www.wantgoo.com/stock/0000/technical-chart"),
        ("nki",    "日經指數",      "https://www.wantgoo.com/global/nki"),
        ("kor",    "韓國綜合",      "https://www.wantgoo.com/global/kor"),
        ("hsi",    "香港恆生",      "https://www.wantgoo.com/global/hsi"),
        ("hsc",    "香港國企",      "https://www.wantgoo.com/global/hsc"),
        ("shi",    "上證Ａ股",      "https://www.wantgoo.com/global/shi"),
        ("sensex", "印度指數",      "https://www.wantgoo.com/global/sen"),
        ("set",    "泰國指數",      "https://www.wantgoo.com/global/set"),
        ("jci",    "印尼指數",      "https://www.wantgoo.com/global/jai"),
    ],
    "美洲與大洋洲": [
        ("sp5",    "標普 500",      "https://www.wantgoo.com/global/sp5"),
        ("nasdaq", "NASDAQ",        "https://www.wantgoo.com/global/nas"),
        ("rut",    "羅素 2000",     "https://www.wantgoo.com/global/rut"),
        ("ibo",    "巴西指數",      "https://www.wantgoo.com/global/ibo"),
        ("alo",    "澳洲指數",      "https://www.wantgoo.com/global/alo"),
    ],
    "歐洲": [
        ("fth",    "英國指數",      "https://www.wantgoo.com/global/fth"),
        ("cac",    "法國指數",      "https://www.wantgoo.com/global/cac"),
        ("dax",    "德國指數",      "https://www.wantgoo.com/global/dax"),
    ],
    "產業與原物料": [
        ("nbi",    "NBI 生技",      "https://www.wantgoo.com/global/nbi"),
        ("xau",    "費城金銀",      "https://www.wantgoo.com/global/xau"),
        ("gold",   "黃金",          "https://www.wantgoo.com/global/gold"),
        ("wti",    "WTI 原油",      "https://www.wantgoo.com/global/wti"),
    ]
}

# 截圖輸出根目錄（桌面，依日期建立子資料夾）
SCRIPT_DIR  = Path(__file__).parent.resolve()
OUTPUT_ROOT = Path.home() / "Desktop" / "玩股網截圖"

# 各週期設定：(檔名後綴, 頁面上對應的按鈕文字)
PERIODS = [
    ("daily",   "日線"),
    ("weekly",  "周線"),
    ("monthly", "月線"),
]

# 圖表主容器 selector
CHART_CONTAINER_SELECTOR = ".technical-charts"
TAB_SELECTOR             = "button.btn.nav-link"

# 逾時設定（毫秒 / 秒）
PAGE_TIMEOUT  = 60_000
INITIAL_WAIT  = 8
SWITCH_WAIT   = 5

# ── 日誌設定 ──────────────────────────────────────────────────────────────────

log_dir  = SCRIPT_DIR / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"markets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ── 核心邏輯 ──────────────────────────────────────────────────────────────────

async def hide_overlays(page):
    """隱藏底部廣告與 Cookie 橫幅等覆蓋元素"""
    await page.evaluate("""
        () => {
            const viewH = window.innerHeight;
            document.querySelectorAll('*').forEach(el => {
                try {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    if (
                        (style.position === 'fixed' || style.position === 'sticky') &&
                        rect.top > viewH * 0.5 &&
                        rect.height > 0 &&
                        rect.width > 0
                    ) {
                        el.style.setProperty('display', 'none', 'important');
                    }
                } catch(e) {}
            });
        }
    """)
    logger.info("已隱藏底部廣告工具列")


async def click_period_tab(page, period_text: str) -> bool:
    """點選對應週期的 Tab 按鈕，返回是否成功"""
    try:
        locator = page.locator(f"{TAB_SELECTOR}:has-text('{period_text}')").first
        if await locator.count() > 0:
            await locator.click()
            logger.info(f"點選「{period_text}」Tab 成功")
            return True
        locator2 = page.locator(f"text='{period_text}'").first
        if await locator2.count() > 0:
            await locator2.click()
            logger.info(f"點選「{period_text}」Tab 成功（fallback）")
            return True
    except Exception as e:
        logger.warning(f"點選「{period_text}」Tab 失敗：{e}")
    logger.warning(f"找不到「{period_text}」Tab 按鈕")
    return False


async def screenshot_chart(page, output_path: Path):
    """
    截取圖表區域（.technical-charts）：
    - visibility:hidden 暫時隱藏 fixed/sticky header（不觸發 canvas reflow）
    - 裁掉底部 Highcharts navigator 列
    """
    try:
        locator = page.locator(CHART_CONTAINER_SELECTOR).first
        if await locator.count() == 0:
            raise ValueError(f"找不到 {CHART_CONTAINER_SELECTOR}")

        # 暫時隱藏 fixed/sticky header
        await page.evaluate("""
            () => {
                window.__hiddenHeaderEls = [];
                document.querySelectorAll('*').forEach(el => {
                    try {
                        const s = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        if ((s.position === 'fixed' || s.position === 'sticky') &&
                            rect.height > 0 && rect.width > 0) {
                            window.__hiddenHeaderEls.push({el, v: el.style.visibility});
                            el.style.visibility = 'hidden';
                        }
                    } catch(e) {}
                });
            }
        """)

        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tf:
            tmp_path = tf.name
        await locator.screenshot(path=tmp_path)

        # 還原 header 可見性
        await page.evaluate("""
            () => {
                (window.__hiddenHeaderEls || []).forEach(({el, v}) => {
                    el.style.visibility = v;
                });
                window.__hiddenHeaderEls = [];
            }
        """)

        # 偵測底部 navigator 高度
        nav_h = await page.evaluate("""
            () => {
                const hc = window.Highcharts;
                if (!hc || !hc.charts) return 0;
                for (const chart of hc.charts) {
                    if (!chart) continue;
                    let maxYBottom = 0;
                    for (const ax of (chart.yAxis || [])) {
                        const b = (ax.top || 0) + (ax.height || 0);
                        if (b > maxYBottom) maxYBottom = b;
                    }
                    if (maxYBottom > 0 && chart.chartHeight > maxYBottom) {
                        const xLabelH = chart.xAxis && chart.xAxis[0] ?
                            Math.ceil(chart.xAxis[0].axisTitleMargin || 20) + 5 : 25;
                        const navHeight = chart.chartHeight - (maxYBottom + xLabelH);
                        if (navHeight > 10) return Math.ceil(navHeight);
                    }
                }
                return 0;
            }
        """)
        if nav_h == 0:
            nav_h = 42  # 實測值：navigator 佔底部約 42px
        logger.info(f"底部裁切量：{nav_h}px")

        try:
            from PIL import Image
            img  = Image.open(tmp_path)
            w, h = img.size
            bottom  = h - nav_h if nav_h > 10 else h
            cropped = img.crop((0, 0, w, bottom))
            cropped.save(str(output_path))
            logger.info(f"截圖成功（{w}x{bottom}，下裁 {nav_h}px）→ {output_path.name}")
        except ImportError:
            import shutil
            shutil.copy(tmp_path, str(output_path))
            logger.warning("PIL 未安裝，使用未裁切原始截圖")
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"截圖失敗：{e}")
        raise


async def process_market(page, market_id: str, market_name: str, url: str, output_dir: Path, selected_periods: list, status_callback=None):
    """處理單一指數：導航至頁面，依序截取選擇的週期"""
    logger.info(f"\n{'─'*50}")
    logger.info(f"開始處理：{market_name}")
    logger.info(f"URL：{url}")
    if status_callback: status_callback(f"載入頁面：{market_name}")

    try:
        await page.goto(url, wait_until="domcontentloaded")
    except Exception as e:
        logger.error(f"{market_name} 頁面載入失敗：{e}")
        if status_callback: status_callback(f"❌ 錯誤：{market_name} 頁面載入失敗")
        return []

    logger.info(f"等待頁面初始渲染（{INITIAL_WAIT} 秒）...")
    import random
    for _ in range(3):
        await page.mouse.move(random.randint(100, 500), random.randint(100, 500))
        await asyncio.sleep(1)
    await asyncio.sleep(INITIAL_WAIT - 3)

    try:
        await page.wait_for_selector(CHART_CONTAINER_SELECTOR, timeout=10_000)
        logger.info("圖表容器已確認存在")
    except PlaywrightTimeoutError:
        logger.warning("圖表容器等待超時，繼續執行")

    generated_files = []

    for suffix, period_text in selected_periods:
        filename = f"{market_id}_{suffix}"
        if status_callback: status_callback(f"正在截取：{market_name} - {period_text}")
        logger.info(f"--- {market_name} / {period_text} ---")

        success = await click_period_tab(page, period_text)
        if success:
            logger.info(f"等待 {SWITCH_WAIT} 秒讓圖表重新渲染...")
            await asyncio.sleep(SWITCH_WAIT)
        else:
            await asyncio.sleep(2)

        # 月線：切換至「10年」時間範圍
        if period_text == "月線":
            logger.info("月線：切換時間範圍至「10年」")
            clicked_10y = False

            # 方法 1：Highcharts rangeSelector API
            try:
                result = await page.evaluate("""
                    () => {
                        const hc = window.Highcharts;
                        if (hc && hc.charts) {
                            for (const chart of hc.charts) {
                                if (!chart) continue;
                                const rs = chart.rangeSelector;
                                if (rs && rs.buttons && rs.buttons.length > 0) {
                                    for (let i = 0; i < rs.buttonOptions.length; i++) {
                                        const label = rs.buttonOptions[i]?.text || '';
                                        if (label.includes('10')) {
                                            rs.clickButton(i, true);
                                            return `Highcharts button[${i}] clicked: ${label}`;
                                        }
                                    }
                                    const lastIdx = rs.buttonOptions.length - 1;
                                    rs.clickButton(lastIdx, true);
                                    return `Highcharts last button[${lastIdx}] clicked`;
                                }
                            }
                        }
                        return null;
                    }
                """)
                if result:
                    logger.info(f"方法1 Highcharts API：{result}")
                    clicked_10y = True
            except Exception as e:
                logger.warning(f"方法1 Highcharts API 失敗：{e}")

            # 方法 2：canvas dispatchEvent
            if not clicked_10y:
                try:
                    box = await page.locator(".technical-charts").first.bounding_box()
                    if box:
                        click_x = box["x"] + 105
                        click_y = box["y"] + 38
                        result = await page.evaluate(f"""
                            () => {{
                                const canvas = document.querySelector('.technical-charts canvas');
                                if (!canvas) return 'no canvas';
                                canvas.dispatchEvent(new MouseEvent('click', {{
                                    bubbles: true, cancelable: true,
                                    clientX: {click_x}, clientY: {click_y}, view: window,
                                }}));
                                return 'dispatched';
                            }}
                        """)
                        logger.info(f"方法2 canvas dispatchEvent：{result}")
                        clicked_10y = True
                except Exception as e:
                    logger.warning(f"方法2 失敗：{e}")

            # 方法 3：Playwright mouse.click
            if not clicked_10y:
                try:
                    box = await page.locator(".technical-charts").first.bounding_box()
                    if box:
                        await page.mouse.click(box["x"] + 105, box["y"] + 38)
                        logger.info("方法3 mouse.click")
                except Exception as e:
                    logger.warning(f"方法3 失敗：{e}")

            if clicked_10y:
                await asyncio.sleep(SWITCH_WAIT)

        await hide_overlays(page)
        output_path = output_dir / f"{filename}.png"
        try:
            await screenshot_chart(page, output_path)
            generated_files.append(output_path)
        except Exception as e:
            logger.error(f"截圖失敗：{e}")
            if status_callback: status_callback(f"❌ {market_name} ({period_text}) 截圖失敗")
            try:
                err_path = output_dir / f"error_{filename}.png"
                await page.screenshot(path=err_path, full_page=True)
                generated_files.append(err_path)
            except:
                pass

    logger.info(f"{market_name} 截圖完成")
    return generated_files


async def run_screenshots(selected_markets, selected_periods, output_dir: Path, status_callback=None):
    """主流程：依序處理所有指數"""
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"=== 開始執行國際指數截圖任務 ===")
    logger.info(f"輸出目錄：{output_dir}")

    vdisplay = None
    if sys.platform.startswith("linux"):
        try:
            from xvfbwrapper import Xvfb
            vdisplay = Xvfb(width=1440, height=900)
            vdisplay.start()
            logger.info("啟動虛擬顯示器 Xvfb")
        except Exception as e:
            logger.warning(f"Xvfb 啟動失敗：{e}")

    all_generated_files = []

    try:
        async with async_playwright() as p:
            is_linux = sys.platform.startswith("linux")
            browser = await p.firefox.launch(
                headless=not is_linux,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                locale="zh-TW",
            )
            page = await context.new_page()
            page.set_default_timeout(PAGE_TIMEOUT)

            for market_id, market_name, url in selected_markets:
                files = await process_market(page, market_id, market_name, url, output_dir, selected_periods, status_callback)
                if files:
                    all_generated_files.extend(files)

            await browser.close()
    finally:
        if vdisplay:
            vdisplay.stop()

    logger.info("\n=== 所有截圖任務完成 ===")
    logger.info(f"檔案位置：{output_dir}")
    return all_generated_files


# ── 入口點 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    today = datetime.now().strftime("%Y-%m-%d")
    output_dir = OUTPUT_ROOT / today
    flat_markets = [m for group in MARKET_GROUPS.values() for m in group]
    asyncio.run(run_screenshots(flat_markets, PERIODS, output_dir))
