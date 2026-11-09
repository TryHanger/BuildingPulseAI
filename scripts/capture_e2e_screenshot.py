import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def run():
    print("Launching Playwright browser...")
    screenshots_dir = Path("docs/screenshots")
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        print("1. Navigating to Monitoring page: http://127.0.0.1:5180/ ...")
        page.goto("http://127.0.0.1:5180/", wait_until="networkidle", timeout=30000)
        time.sleep(3)

        # 1. Monitoring page normal LBNL
        mon_path = "docs/screenshots/stage3_monitoring_lbnl_normal.png"
        page.screenshot(path=mon_path, full_page=True)
        print(f"Captured: {mon_path}")

        # 2. Switch to Diagnostics Tab
        print("2. Switching to Diagnostics tab...")
        diag_tab_btn = page.query_selector("button:has-text('Диагностика')")
        if diag_tab_btn:
            diag_tab_btn.click()
            time.sleep(3)

        # Diagnostics Viewport 1440x900
        vp_path = "docs/screenshots/stage3_diagnostics_viewport.png"
        page.screenshot(path=vp_path, full_page=False)
        print(f"Captured viewport: {vp_path}")

        # 3. Select Faulted Scenario: coi_stuck_025
        print("3. Selecting Faulted LBNL scenario (coi_stuck_025)...")
        sc_select = page.query_selector("select")
        if sc_select:
            # Look for coi_stuck_025
            options = page.query_selector_all("select option")
            for opt in options:
                txt = opt.inner_text()
                if "coi_stuck_025" in txt or "VALVE_STUCK" in txt:
                    val = opt.get_attribute("value")
                    sc_select.select_option(val)
                    time.sleep(3)
                    break

        fault_path = "docs/screenshots/stage3_diagnostics_lbnl_valve_stuck.png"
        page.screenshot(path=fault_path, full_page=True)
        print(f"Captured faulted scenario: {fault_path}")

        # 4. Select Synthetic Demo scenario for Domain Guard
        print("4. Selecting Synthetic Demo scenario for Domain Guard test...")
        sc_select = page.query_selector("select")
        if sc_select:
            options = page.query_selector_all("select option")
            for opt in options:
                txt = opt.inner_text()
                if "synthetic" in txt.lower():
                    val = opt.get_attribute("value")
                    sc_select.select_option(val)
                    time.sleep(3)
                    break

        guard_path = "docs/screenshots/stage3_diagnostics_synthetic_domain_guard.png"
        page.screenshot(path=guard_path, full_page=True)
        print(f"Captured synthetic domain guard: {guard_path}")

        browser.close()
        print("Playwright screenshots capture completed successfully.")

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"Playwright error: {e}")
