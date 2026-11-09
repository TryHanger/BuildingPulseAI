"""Run real Chromium checks and capture desktop/mobile evidence screenshots."""
import argparse
from datetime import datetime
from pathlib import Path
import re

from playwright.sync_api import expect, sync_playwright

from oracle import read_stage09

API = "/api/research/field-evidence"
PAGE = "/research/field-evidence"
OBSERVED = "BAS_ON_TO_OFF_OBSERVED"
NO_CHANGE = "NO_OBSERVED_CHANGE"


def rows(outcome, ticks):
    start = datetime.fromisoformat(outcome["start_naive"])
    for tick in ticks:
        minute = int((datetime.fromisoformat(tick["native_time"]) - start).total_seconds()) // 60
        yield [tick["partition"], tick["native_time"], f"{minute:+d} мин" if minute > 0 else f"{minute} мин",
               *({"0": "OFF", "1": "ON", "": "—"}[tick[key]]
                 for key in ("supply", "exhaust", "heat_request", "cool_request")),
               tick["supply_evidence"], tick["paired_evidence"]]


def check_window(page, outcome, ticks):
    page.get_by_role("combobox", name="Установка", exact=True).select_option(outcome["ahu"])
    page.get_by_role("combobox", name="Окно", exact=True).select_option(outcome["replay_id"])
    summary = page.locator("summary", has_text="Все отсчёты")
    if summary.locator("..").get_attribute("open") is None:
        summary.click()
    table = page.get_by_role("region", name="Таблица отсчётов BAS")
    assert [row.locator("td").all_text_contents() for row in table.locator("tbody tr").all()] == list(rows(outcome, ticks))
    timeline = page.get_by_role("region", name="Временная шкала BAS")
    bounds = f'{outcome["start_naive"]} → {outcome["end_naive_exclusive"]} (конец исключён)'
    expect(timeline.get_by_text(bounds, exact=True)).to_be_visible()
    for key in ("A", "B"):
        article = page.get_by_role("article", name=f"Правило {key}")
        change = outcome[key + "_change"]
        text = {
            OBSERVED: "Наблюдался переход ON → OFF",
            NO_CHANGE: "Парный переход не наблюдался" if key == "B" else "Переход притока не наблюдался",
            "ABSTAIN": "ABSTAIN · вывод о переходе недоступен",
        }[change]
        expect(article.get_by_text(text, exact=True)).to_be_visible()
        if change == OBSERVED:
            expect(article.get_by_text("+5 мин", exact=True)).to_be_visible()
            expect(article.get_by_text("+10 мин", exact=True)).to_be_visible()
        disclosure = article.locator("summary", has_text="Поля исхода Stage09")
        if disclosure.locator("..").get_attribute("open") is None:
            disclosure.click()
        raw = {pair.locator("dt").inner_text(): pair.locator("dd").inner_text()
               for pair in article.locator("details dl > div").all()}
        assert raw == {k: v or "—" for k, v in outcome.items() if k.startswith(key + "_")}
        disclosure.click()
    summary.click()
    print("PASS browser render and all 20 visible ticks:", outcome["replay_id"])


def check_layout(page):
    assert page.evaluate("document.documentElement.scrollWidth === innerWidth")
    assert page.get_by_role("heading", name="Полевые свидетельства BAS").is_visible()
    assert page.get_by_text("UNKNOWN_CLOCK_NAIVE_WORKBOOK_300S", exact=True).is_visible()


def run(base, stage09, output):
    expected, manifest, _ = read_stage09(stage09)
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base + "/research", wait_until="domcontentloaded")
        page.get_by_role("link", name="Полевые свидетельства · BAS").click()
        expect(page).to_have_url(base + PAGE)
        select = page.get_by_role("combobox", name="Установка", exact=True)
        expect(select).to_be_visible()
        assert select.locator("option").all_text_contents() == ["AHU1", "AHU2", "AHU8", "AHU18", "AHU23", "AHU24"]
        select.focus()
        page.keyboard.press("ArrowDown")
        expect(select).to_have_value("AHU2")
        page.keyboard.press("Tab")
        expect(page.get_by_role("combobox", name="Окно", exact=True)).to_be_focused()
        select.select_option("AHU1")
        check_layout(page)
        page.screenshot(path=output / "desktop-ahu1.png", full_page=True)

        for outcome, ticks in expected.values():
            check_window(page, outcome, ticks)
        select.select_option("AHU23")
        expect(page.get_by_text("Вытяжка сообщает ON", exact=False)).to_be_visible()
        expect(page.get_by_text("Независимого подтверждения по перепаду давления нет.", exact=False)).to_be_visible()
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=output / "desktop-ahu23-intervention.png", full_page=True)
        compare = page.get_by_role("region", name="Подобранные контроли · AHU23")
        expect(compare.get_by_text("18/18 отсчётов", exact=False)).to_have_count(2)
        compare.get_by_role("button", name="Контроль · +77 дн.").click()
        expect(page.get_by_role("combobox", name="Окно", exact=True)).to_have_value("control-AHU23-077")
        expect(compare.get_by_role("button", name="Контроль · +77 дн.")).to_have_attribute("aria-pressed", "true")
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=output / "desktop-ahu23-control.png", full_page=True)

        mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True)
        mobile.on("pageerror", lambda error: errors.append(str(error)))
        mobile.goto(base + PAGE)
        mobile.get_by_role("combobox", name="Установка", exact=True).select_option("AHU24")
        expect(mobile.get_by_text("Перед окном вытяжка уже сообщает OFF.", exact=False)).to_be_visible()
        provenance = mobile.locator("summary", has_text="Паспорт источника")
        provenance.click()
        source = manifest["files"]["AHU24.xlsx"]
        for value in (source["file_id"], source["publisher_sha256"], "logic__real_value__fan_exahust_air", "bas-fan-observation@1.0.0"):
            expect(provenance.locator("..").get_by_text(value, exact=True)).to_be_visible()
        check_layout(mobile)
        mobile.evaluate("window.scrollTo(0, 0)")
        mobile.screenshot(path=output / "mobile-ahu24-provenance.png", full_page=True)

        mobile.get_by_role("combobox", name="Установка", exact=True).select_option("AHU8")
        expect(mobile.get_by_text("ABSTAIN · вывод о переходе недоступен", exact=True)).to_have_count(2)
        expect(mobile.get_by_text("Статусы вентиляторов отсутствуют", exact=False).first).to_be_visible()
        check_layout(mobile)
        mobile.evaluate("window.scrollTo(0, 0)")
        mobile.screenshot(path=output / "mobile-ahu8-missing.png", full_page=True)

        # Exercise the UI's fail-closed branch independently of server bundle mutation tests.
        page.route(re.compile(r"/api/research/field-evidence$"), lambda route: route.fulfill(
            status=503, json={"detail": "SOURCE_PROVENANCE_UNVERIFIED"}))
        page.reload(wait_until="domcontentloaded")
        expect(page.get_by_role("alert")).to_contain_text("SOURCE_PROVENANCE_UNVERIFIED")
        expect(page.get_by_role("combobox", name="Установка", exact=True)).to_have_count(0)
        expect(page.get_by_role("heading", name="Временная шкала BAS")).to_have_count(0)
        assert not errors, errors
        print("PASS discoverability, keyboard, matched controls, provenance, fail-closed UI and 1440/390 px layouts")
        print("Chromium", browser.version)
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage09", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--base", default="http://127.0.0.1:5180")
    args = parser.parse_args()
    run(args.base, args.stage09, args.output)
