"""Exercise the separate, real G36 Investigator route."""
import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width, height in [(1440, 900), (390, 844)]:
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(args.url)
            page.get_by_role("link", name="Сценарий G36-5wk").click()
            expect(page.get_by_role("heading", name="Устойчивое превышение SAT над уставкой при запросе охлаждения")).to_be_visible()
            expect(page.get_by_text("SIMULATED_BENCHMARK · G36-5wk", exact=True)).to_be_visible()
            expect(page.get_by_text("Применимо 7428 из 7920", exact=True)).to_be_visible()
            table = page.get_by_role("table")
            expect(table.get_by_role("row", name="Заданное открытие наружной заслонки", exact=False)).to_contain_text("305")
            expect(table.get_by_role("row", name="Заданная утечка воздуховода", exact=False)).to_contain_text("510")
            expect(page.get_by_text("REFERENCE_ORACLE", exact=False)).to_have_count(0)
            slider = page.get_by_role("slider", name="Курсор модели")
            slider.fill("40")
            expect(page.get_by_text("Модельное время 16366800 с", exact=False)).to_be_visible()
            expect(page.get_by_text("Температурный симптом подтверждён", exact=True)).to_be_visible()
            page.get_by_label("Панель").select_option("EXTRA_SIMULATED")
            expect(page.get_by_text("REFERENCE_ORACLE · Положение клапана в симуляции 0", exact=False)).to_be_visible()
            slider.fill("40")
            expect(page.get_by_text("Температурный симптом подтверждён", exact=True)).to_be_visible()
            expect(page.locator("canvas")).to_have_count(2)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=args.output / f"g53-investigator-{width}.png", full_page=True)
            page.get_by_label("Прогон", exact=True).select_option("NOMINAL")
            expect(page.get_by_text("Применимо 2800 из 7920", exact=True)).to_be_visible()
            expect(page.get_by_text("Номинальная симуляция", exact=False)).to_be_visible()
            assert not errors, errors
            page.get_by_label("Прогон", exact=True).select_option("DUCT_LEAK")
            expect(page.get_by_text("Применимо 2808 из 7920", exact=True)).to_be_visible()
            page.get_by_role("link", name="Открыть Investigator LBNL").click()
            expect(page.get_by_role("heading", name="AHU Investigator", exact=True)).to_be_visible()
            page.close()
            print(f"PASS G36 real source, roles, time and LBNL navigation at {width}×{height}", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
