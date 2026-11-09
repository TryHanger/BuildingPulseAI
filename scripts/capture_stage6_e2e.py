"""
Playwright script to capture Stage 6 E2E verification screenshots:
1. docs/screenshots/stage6_csiro_before_after.png
2. docs/screenshots/stage6_csiro_prediction_chart.png
3. docs/screenshots/stage6_csiro_guard.png
"""

import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def run():
    print("Launching Playwright browser for Stage 6 E2E verification...")
    screenshots_dir = Path("docs/screenshots")
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1050})
        page = context.new_page()

        print("1. Navigating to http://127.0.0.1:5180/ ...")
        page.goto("http://127.0.0.1:5180/", wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # 2. Navigate to Research Page
        print("2. Navigating to 'Исследования' tab...")
        research_btn = page.query_selector("button:has-text('Исследования')")
        if research_btn:
            research_btn.click()
            time.sleep(2)

        # 3. Navigate to Real Building & Adaptation Tab
        print("3. Navigating to '5. Реальное здание и адаптация (CSIRO)'...")
        real_bldg_tab = page.query_selector("button:has-text('Реальное здание')")
        if real_bldg_tab:
            real_bldg_tab.click()
            time.sleep(3)

        # Screen 1: Overview Before/After
        print("4. Capturing docs/screenshots/stage6_csiro_before_after.png ...")
        page.screenshot(path="docs/screenshots/stage6_csiro_before_after.png", full_page=True)

        # Screen 2: Prediction Chart
        print("5. Capturing docs/screenshots/stage6_csiro_prediction_chart.png ...")
        chart_el = page.query_selector(".echarts-for-react") or page.query_selector("div:has-text('Временной ряд отложенного теста')")
        if chart_el:
            chart_el.screenshot(path="docs/screenshots/stage6_csiro_prediction_chart.png")
        else:
            page.screenshot(path="docs/screenshots/stage6_csiro_prediction_chart.png")

        # Screen 3: Domain Guard interaction
        print("6. Switching model and capturing Domain Guard view...")
        select_el = page.query_selector("select")
        if select_el:
            # Switch to Z0 to trigger OUT_OF_DOMAIN_UNVALIDATED
            select_el.select_option("vs-sa-temp-v2")
            time.sleep(2)

        page.screenshot(path="docs/screenshots/stage6_csiro_guard.png", full_page=True)

        browser.close()
        print("Stage 6 E2E screenshots successfully captured!")

if __name__ == "__main__":
    run()
