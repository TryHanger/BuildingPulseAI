"""G3 route regression through the G4 feed. The synthetic positive path lives in test_playwright_g4.py."""
import argparse
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ANNUAL = "ds_8e5b1ddfdd14"
OBSERVATION = "2018-01-02T11:08:00"
ZERO = "В проверенном окне подтверждённых симптомов нет"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5180")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width, height in ((1440, 900), (1280, 800), (1024, 768), (390, 844)):
            page = browser.new_page(viewport={"width": width, "height": height}, timezone_id="Asia/Qyzylorda")
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(args.url)
            page.get_by_role("button", name="Инциденты · LBNL").click()
            expect(page.get_by_role("heading", name="Инциденты LBNL SD-AHU")).to_be_visible()
            page.get_by_label("Датасет").select_option(ANNUAL)
            page.get_by_label("Начало окна (время источника)").fill(OBSERVATION)
            page.get_by_role("button", name="Проверить окно").click()
            expect(page.get_by_text(ZERO, exact=True)).to_be_visible()
            expect(page.get_by_text(re.compile(r"^[1-9]\d* из 480$"))).to_be_visible()
            expect(page.get_by_text("VERIFIED_RUNTIME · SOURCE_SIMULATION_TIME", exact=True)).to_be_visible()
            expect(page.get_by_role("link", name="Открыть подтверждающий отсчёт")).to_have_count(0)
            overflow = page.evaluate("""() => Array.from(document.querySelectorAll('main *'))
                .filter(node => node.getBoundingClientRect().right > innerWidth + 1)
                .map(node => [node.tagName, node.className, node.getBoundingClientRect().right])""")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), overflow
            assert not errors, errors
            page.screenshot(path=args.output / f"g3-live-incidents-{width}x{height}.png", full_page=True)
            if width == 1440:
                page.get_by_role("link", name="Архивная демо-лента").click()
                expect(page.get_by_text("DEMO_FIXTURE · UI_MOCK_V0", exact=False)).to_be_visible()
                page.get_by_role("link", name="Открыть ленту LBNL").click()
                expect(page.get_by_role("heading", name="Инциденты LBNL SD-AHU")).to_be_visible()
                page.get_by_role("button", name="Мониторинг (Stage 1)").click()
                expect(page.get_by_text("LEGACY_ANALYSIS · прежний API", exact=False)).to_be_visible()
            page.close()
            print(f"PASS live verified empty feed, scoped coverage and viewport {width}x{height}", flush=True)

        page = browser.new_page()
        page.route("**/api/v1/investigation?*", lambda route: route.fulfill(status=409, json={
            "detail": {"code": "INCIDENT_INDEX_INTEGRITY", "message": "Injected test response"}
        }))
        page.goto(f"{args.url}/incidents")
        expect(page.get_by_role("alert")).to_contain_text("INCIDENT_INDEX_INTEGRITY")
        expect(page.get_by_text(ZERO, exact=True)).to_have_count(0)
        browser.close()
        print("PASS index failure stays visible without false empty result", flush=True)


if __name__ == "__main__":
    main()
