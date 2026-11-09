import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def run():
    print("Launching Playwright browser for Stage 5 E2E verification...")
    screenshots_dir = Path("docs/screenshots")
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 960})
        page = context.new_page()

        print("1. Navigating to http://127.0.0.1:5180/ ...")
        page.goto("http://127.0.0.1:5180/", wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # 2. Navigate to Research Page
        print("2. Navigating to 'Исследования' tab...")
        research_btn = page.query_selector("button:has-text('Исследования')")
        if research_btn:
            research_btn.click()
            time.sleep(3)

        # Screen 1: Research Overview (H1, H2, H3, External Transfer)
        print("3. Capturing Stage 5 Research Overview...")
        page.screenshot(path="docs/screenshots/stage5_research_overview.png", full_page=True)
        print("Captured: docs/screenshots/stage5_research_overview.png")

        # Screen 2: Risk-Coverage Tab
        print("4. Capturing Risk-Coverage tab...")
        tab2 = page.query_selector("button:has-text('Селективный риск')")
        if tab2:
            tab2.click()
            time.sleep(2)
            page.screenshot(path="docs/screenshots/stage5_research_risk_coverage.png", full_page=True)
            print("Captured: docs/screenshots/stage5_research_risk_coverage.png")

        # Screen 3: Recommender Simulator Tab
        print("5. Capturing Recommender simulator tab...")
        tab4 = page.query_selector("button:has-text('Рекомендатель датчиков')")
        if tab4:
            tab4.click()
            time.sleep(2)
            page.screenshot(path="docs/screenshots/stage5_research_recommender.png", full_page=True)
            print("Captured: docs/screenshots/stage5_research_recommender.png")

        # Screen 4: Real Building (CSIRO) Tab
        print("6. Capturing Real Building (CSIRO) tab...")
        tab5 = page.query_selector("button:has-text('Реальное здание')")
        if tab5:
            tab5.click()
            time.sleep(2)
            page.screenshot(path="docs/screenshots/stage5_research_real_building.png", full_page=True)
            print("Captured: docs/screenshots/stage5_research_real_building.png")

        # Screen 5: Diagnostics Page with Recommender Action
        print("7. Switching to Diagnostics page to verify inline recommendation trigger...")
        diag_btn = page.query_selector("button:has-text('Диагностика')")
        if diag_btn:
            diag_btn.click()
            time.sleep(3)

            # Click the recommendation button in Card 2 if present
            rec_btn = page.query_selector("button:has-text('Какое измерение поможет?')")
            if rec_btn:
                print("Clicking 'Какое измерение поможет?' button...")
                rec_btn.click()
                time.sleep(2)

            page.screenshot(path="docs/screenshots/stage5_diagnostics_recommender_action.png", full_page=True)
            print("Captured: docs/screenshots/stage5_diagnostics_recommender_action.png")

        browser.close()
        print("E2E screenshot capture completed successfully!")

if __name__ == "__main__":
    run()
