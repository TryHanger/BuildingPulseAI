import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def run():
    print("Launching Playwright browser for Stage 4 E2E verification...")
    screenshots_dir = Path("docs/screenshots")
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        print("1. Navigating to http://127.0.0.1:5180/ ...")
        page.goto("http://127.0.0.1:5180/", wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # 2. Switch to Diagnostics Tab
        print("2. Switching to Diagnostics tab...")
        diag_tab_btn = page.query_selector("button:has-text('Диагностика')")
        if diag_tab_btn:
            diag_tab_btn.click()
            time.sleep(3)

        # Viewport screenshot of Stage 4 Diagnostics
        vp_path = "docs/screenshots/stage4_diagnostics_viewport.png"
        page.screenshot(path=vp_path, full_page=False)
        print(f"Captured: {vp_path}")

        # 3. Select Faulted Scenario: coi_bias_-2_annual.csv to demonstrate Ambiguity / Refutation
        print("3. Selecting coi_bias_-2_annual scenario...")
        selects = page.query_selector_all("select")
        sc_select = selects[0] if len(selects) > 0 else None
        prof_select = selects[1] if len(selects) > 1 else None

        if sc_select:
            options = sc_select.query_selector_all("option")
            for opt in options:
                txt = opt.inner_text()
                if "coi_bias_-2" in txt or "SENSOR_BIAS_NEG_2C" in txt:
                    val = opt.get_attribute("value")
                    sc_select.select_option(val)
                    time.sleep(3)
                    break

        # In BASIC profile:
        basic_path = "docs/screenshots/stage4_diagnostics_basic_ambiguity.png"
        page.screenshot(path=basic_path, full_page=True)
        print(f"Captured: {basic_path}")

        # 4. Switch Profile to BASIC_PLUS_VALVE on coi_stuck_025
        print("4. Switching scenario to coi_stuck_025 and profile to BASIC_PLUS_VALVE...")
        if sc_select:
            options = sc_select.query_selector_all("option")
            for opt in options:
                txt = opt.inner_text()
                if "coi_stuck_025" in txt or "VALVE_STUCK" in txt:
                    val = opt.get_attribute("value")
                    sc_select.select_option(val)
                    time.sleep(2)
                    break

        if prof_select:
            prof_select.select_option("BASIC_PLUS_VALVE")
            time.sleep(3)

        valve_path = "docs/screenshots/stage4_diagnostics_valve_feedback_single_cause.png"
        page.screenshot(path=valve_path, full_page=True)
        print(f"Captured: {valve_path}")

        # 5. Domain Guard Verification on Synthetic Demo
        print("5. Selecting Synthetic Demo to verify Domain Guard...")
        if sc_select:
            options = sc_select.query_selector_all("option")
            for opt in options:
                txt = opt.inner_text()
                if "synthetic" in txt.lower():
                    val = opt.get_attribute("value")
                    sc_select.select_option(val)
                    time.sleep(2)
                    break

        guard_path = "docs/screenshots/stage4_diagnostics_synthetic_domain_guard.png"
        page.screenshot(path=guard_path, full_page=True)
        print(f"Captured: {guard_path}")

        # 6. Capture Research Tables Section
        print("6. Capturing Stage 4 research benchmark section...")
        # Select an LBNL benchmark scenario back
        if sc_select:
            options = sc_select.query_selector_all("option")
            for opt in options:
                txt = opt.inner_text()
                if "lbnl_AHU_annual" in txt:
                    val = opt.get_attribute("value")
                    sc_select.select_option(val)
                    time.sleep(2)
                    break

        tables_path = "docs/screenshots/stage4_diagnostics_research_tables.png"
        page.screenshot(path=tables_path, full_page=True)
        print(f"Captured: {tables_path}")

        browser.close()
        print("All Stage 4 Playwright screenshots captured successfully!")

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"Playwright error: {e}")
        sys.exit(1)
