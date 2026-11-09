"""Exercise G36-1wk BASIC and EXTRA on the Investigator route."""
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
            page.get_by_label("Профиль G36").select_option("g36-1wk")
            expect(page.get_by_text("SIMULATED_BENCHMARK · G36-1wk", exact=True)).to_be_visible()
            expect(page.get_by_text("UNPAIRED_DESCRIPTIVE · NOT_BLIND_PREVIEWED_SOURCE · MODEL_SECONDS", exact=True)).to_be_visible()
            expect(page.get_by_text("Причина не установлена.", exact=False)).to_be_visible()
            expect(page.get_by_text("Применимо 8391 из 10081", exact=True)).to_be_visible()
            expect(page.get_by_text("Отдельная описательная оценка · PASS · Парная причинная оценка · STOP")).to_be_visible()
            expect(page.get_by_text("На сценарий приходится 1 симуляционный прогон.", exact=False)).to_be_visible()
            expect(page.get_by_text("Начала подтверждений 4", exact=True)).to_be_visible()
            expect(page.get_by_label("Панель")).to_have_value("BASIC")
            expect(page.get_by_text("SOURCE_ORACLE_EXCEPTION", exact=False)).to_have_count(0)
            expect(page.get_by_text("REFERENCE_ORACLE", exact=False)).to_have_count(0)
            seek = page.get_by_label("Начало окна, модельные секунды")
            seek.fill("17647920")
            page.get_by_role("button", name="Открыть окно").click()
            expect(page.get_by_text("Модельное время 17647920 с", exact=False)).to_be_visible()
            expect(page.get_by_text("Температурный симптом подтверждён", exact=True)).to_be_visible()
            page.get_by_text("Ограничения сопоставимости и метки", exact=True).click()
            expect(page.get_by_text("Парное сравнение заблокировано.", exact=False)).to_be_visible()
            requests = []
            page.on("request", lambda request: requests.append(request.method))
            page.get_by_text("Sensor Lab · границы наблюдаемости", exact=True).click()
            expect(page.get_by_text("Физическое охлаждение неизвестно (UNKNOWN). Причина не установлена.", exact=True)).to_be_visible()
            expect(page.get_by_text("FIELD_RECORDED_UNMAPPED", exact=True)).to_have_count(3)
            expect(page.get_by_text("PUBLISHED_SIMULATION", exact=True)).to_have_count(2)
            expect(page.get_by_text("NOT_AVAILABLE", exact=True)).to_be_visible()
            expect(page.get_by_text("ORACLE_FORBIDDEN", exact=True)).to_be_visible()
            expect(page.get_by_text("перепадом через охладитель.", exact=False)).to_be_visible()
            simulation = page.get_by_role("region", name="SIMULATION · G36", exact=True)
            field = page.get_by_role("region", name="FIELD · RBC-Nesbitt", exact=True)
            expect(simulation.get_by_text("Исследовательская переменная EXTRA_SIMULATED.", exact=False)).to_be_visible()
            expect(simulation.get_by_text("FIELD_RECORDED_UNMAPPED", exact=True)).to_have_count(0)
            expect(field.get_by_text("PUBLISHED_SIMULATION", exact=True)).to_have_count(0)
            expect(field.get_by_text("HYDRONIC_SCOPE_UNVERIFIED", exact=False)).to_contain_text("Ветвевой расход AHU2 не подтверждён.")
            section_context = page.get_by_role("complementary", name="SIM_ONLY_SECTION_CONTEXT")
            expect(section_context).to_contain_text("превышение уставки SAT уже наблюдалось на выходе охладителя")
            expect(section_context).to_contain_text("причина и польза для диагностики не установлены")
            expect(section_context.get_by_role("button")).to_have_count(0)
            assert not requests, requests
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=args.output / f"g60-basic-{width}.png", full_page=True)
            page.get_by_label("Панель").select_option("EXTRA_SIMULATED")
            seek.fill("18230340")
            page.get_by_role("button", name="Открыть окно").click()
            expect(page.get_by_text("Модельное время 18230340 с", exact=False)).to_be_visible()
            oracle = page.get_by_text("REFERENCE_ORACLE · Положение клапана в симуляции 1", exact=False)
            expect(oracle).to_contain_text("SOURCE_ORACLE_EXCEPTION")
            page.get_by_role("slider", name="Курсор модели").fill("1")
            expect(page.get_by_text("Модельное время 18230400 с", exact=False)).to_be_visible()
            expect(oracle).to_contain_text("SOURCE_ORACLE_EXCEPTION")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=args.output / f"g60-extra-tail-{width}.png", full_page=True)
            page.get_by_label("Панель").select_option("BASIC")
            page.get_by_label("Прогон", exact=True).select_option("NOMINAL")
            expect(page.get_by_text("Применимо 5423 из 10081", exact=True)).to_be_visible()
            expect(page.get_by_text("Подтверждённые отсчёты 0", exact=False)).to_be_visible()
            assert not errors, errors
            page.close()
            print(f"PASS G6.0 BASIC, direct seek, EXTRA tail and nominal run at {width}×{height}", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
