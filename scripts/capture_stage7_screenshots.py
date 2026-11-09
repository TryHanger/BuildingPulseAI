"""
BuildingPulse AI — Stage 7 Playwright E2E Screenshot Capture (Gate 3 & Gate 6)
Captures real high-resolution screenshots of the diploma prototype:
  1. stage7_monitoring_ahu.png
  2. stage7_diagnostics_fault.png
  3. stage7_research_overview.png
  4. stage7_research_csiro_prediction.png (Showing night gaps break and fault mark areas)
  5. stage7_research_csiro_table.png (Showing truthful H4b and H4c metrics)
  6. stage7_research_recommender.png
"""

import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def capture():
    print("Launching Chromium for Stage 7 screenshots...")
    out_dir = Path("docs/screenshots")
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 1440x900 desktop viewport
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 1. Monitoring Screen
        print("1. Capturing Monitoring Page...")
        page.goto("http://127.0.0.1:5180/", wait_until="networkidle", timeout=30000)
        time.sleep(2)
        mon_path = out_dir / "stage7_monitoring_ahu.png"
        page.screenshot(path=str(mon_path), full_page=True)
        print(f"  Saved: {mon_path}")

        # 2. Diagnostics Screen
        print("2. Capturing Diagnostics Page...")
        diag_btn = page.query_selector("button:has-text('Диагностика')")
        if diag_btn:
            diag_btn.click()
            time.sleep(3)
        diag_path = out_dir / "stage7_diagnostics_fault.png"
        page.screenshot(path=str(diag_path), full_page=True)
        print(f"  Saved: {diag_path}")

        # 3. Research Page - Overview
        print("3. Capturing Research Page (Overview)...")
        res_btn = page.query_selector("button:has-text('Исследования')")
        if res_btn:
            res_btn.click()
            time.sleep(2)
        res_ov_path = out_dir / "stage7_research_overview.png"
        page.screenshot(path=str(res_ov_path), full_page=True)
        print(f"  Saved: {res_ov_path}")

        # 4. Research Page - CSIRO AHU9 (Real Building)
        print("4. Capturing CSIRO AHU9 Tab (Prediction chart with night gaps)...")
        csiro_tab_btn = page.query_selector("button:has-text('Реальное здание CSIRO')")
        if csiro_tab_btn:
            csiro_tab_btn.click()
            time.sleep(4)
        csiro_pred_path = out_dir / "stage7_research_csiro_prediction.png"
        page.screenshot(path=str(csiro_pred_path), full_page=True)
        print(f"  Saved: {csiro_pred_path}")

        # 5. Research Page - CSIRO Table & Conclusions viewport
        print("5. Capturing CSIRO Table & Limitations...")
        tbl_el = page.query_selector("table")
        if tbl_el:
            tbl_path = out_dir / "stage7_research_csiro_table.png"
            tbl_el.screenshot(path=str(tbl_path))
            print(f"  Saved: {tbl_path}")

        # 6. Research Page - Sensor Recommender
        print("6. Capturing Sensor Recommender Tab...")
        rec_tab_btn = page.query_selector("button:has-text('Рекомендатель')")
        if rec_tab_btn:
            rec_tab_btn.click()
            time.sleep(2)
        rec_path = out_dir / "stage7_research_recommender.png"
        page.screenshot(path=str(rec_path), full_page=True)
        print(f"  Saved: {rec_path}")

        browser.close()
        print("All Stage 7 screenshots captured successfully!")

if __name__ == "__main__":
    capture()
