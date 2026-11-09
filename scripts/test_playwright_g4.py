"""Exercise both engineering paths through real HTTP and Chromium."""
import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from playwright.sync_api import expect, sync_playwright

ANNUAL = "ds_8e5b1ddfdd14"
CONFIRMED = "2018-01-02T11:15:00"
MID = "2018-01-02T11:17:00"
BEFORE = "2018-01-02T11:10:00"
GAP = "2018-01-02T11:32:00"


def no_overflow(page):
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), page.evaluate(
        """() => [...document.querySelectorAll('main *')]
        .filter(node => node.getBoundingClientRect().right > innerWidth + 1)
        .map(node => [node.tagName, node.className]).slice(0, 20)"""
    )


def capture_reports(request, url, output):
    for name, query in [
        ("demo", "dataset_id=demo-g4-mat"),
        ("lbnl", f"dataset_id={ANNUAL}&start=2018-01-02T11:08:00"),
    ]:
        endpoint = f"{url}/api/v1/investigation?{query}"
        json_response = request.get(endpoint)
        assert json_response.ok
        payload = json_response.json()
        for fmt in ("json", "html"):
            target = f"{endpoint}&format={fmt}"
            first = request.get(target)
            assert first.ok and first.body() == request.get(target).body()
            assert payload["source_sha256"].encode() in first.body()
            assert payload["run_sha256"].encode() in first.body()
            (output / f"{name}-report.{fmt}").write_bytes(first.body())
    g3 = request.get(f"{url}/api/v1/incidents?dataset_id={ANNUAL}")
    assert g3.ok and g3.json()["events"] == [] and g3.json()["result_origin"] == "VERIFIED_RUNTIME"


def assert_chart_gaps(page):
    # Use the ECharts instance created by the app's Vite-served module.
    result = page.evaluate(r"""async () => {
      const wrapper = performance.getEntriesByType('resource').find(row => row.name.includes('/echarts-for-react.js'));
      const script = await (await fetch(wrapper.name)).text();
      const chunk = script.match(/echarts_exports\s*\} from "([^"]+)"/)[1];
      const { echarts_exports } = await import(chunk);
      const charts = [...document.querySelectorAll('[_echarts_instance_]')];
      const series = charts.flatMap(node => echarts_exports.getInstanceByDom(node).getOption().series);
      return series.map(item => ({ name: item.name, connectNulls: item.connectNulls,
        gaps: item.data.filter(point => point[1] === null).map(point => point[0]) }));
    }""")
    assert len(result) == 5 and all(row["connectNulls"] is False and row["gaps"] == [1290] for row in result), result
    print("PASS five plotted source channels have an explicit null across the ten missing minutes", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5180")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--missing-mat-api", help="Separate backend serving the generated negative fixture")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    screenshots = args.output / "screenshots"
    screenshots.mkdir(exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        capture_reports(playwright.request.new_context(), args.url, args.output)
        for width, height in ((1440, 900), (1280, 800), (1024, 768), (390, 844)):
            page = browser.new_page(viewport={"width": width, "height": height}, timezone_id="Asia/Qyzylorda")
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"{args.url}/incidents")
            page.get_by_label("Датасет").select_option(ANNUAL)
            page.get_by_label("Начало окна (время источника)").fill("2018-01-02T11:08:00")
            page.get_by_role("button", name="Проверить окно").click()
            expect(page.get_by_text("В проверенном окне подтверждённых симптомов нет", exact=True)).to_be_visible()
            expect(page.get_by_text("35,62% (187192 из 525540)", exact=False)).to_be_visible()
            expect(page.get_by_text("Подтверждённые эпизоды", exact=True).locator("..").get_by_role("definition")).to_have_text("0")
            expect(page.get_by_text("HEALTHY", exact=True)).to_have_count(0)
            no_overflow(page)
            page.screenshot(path=screenshots / f"g4-lbnl-{width}.png", full_page=True)

            page.get_by_role("link", name="Открыть синтетический эпизод G4").click()
            expect(page.get_by_text("DEMO_FIXTURE · G4", exact=False)).to_be_visible()
            expect(page.get_by_text("Demo Fixture (UI_MOCK_V0)", exact=True)).to_have_count(0)
            expect(page.get_by_text("Evidence Inspector · 5 каналов · 55 отсчётов", exact=True)).to_be_visible()
            page.get_by_text("Evidence Inspector · 5 каналов · 55 отсчётов", exact=True).click()
            page.get_by_text("MA_TEMP · MEASUREMENT · 11 наблюдений", exact=True).click()
            expect(page.get_by_text("18 degF", exact=False)).to_have_count(11)
            no_overflow(page)
            with page.expect_popup() as popup:
                page.get_by_role("link", name="Открыть HTML-отчёт").first.click()
            report = popup.value
            expect(report.get_by_role("heading", name="BuildingPulse engineering investigation")).to_be_visible()
            expect(report.get_by_text("DEMO_FIXTURE · DEMO_FIXTURE", exact=False)).to_be_visible()
            report.close()
            with page.expect_download() as download:
                page.get_by_role("link", name="Скачать JSON").first.click()
            assert json.loads(Path(download.value.path()).read_bytes())["provenance"] == "DEMO_FIXTURE"
            page.get_by_role("link", name="Открыть подтверждающий отсчёт").click()
            expect(page.get_by_text(CONFIRMED, exact=True).first).to_be_visible()
            cursor = page.get_by_role("region", name="Расследование по курсору")
            expect(cursor.get_by_text("Подтверждённые эпизоды", exact=True).locator("..").get_by_role("definition")).to_have_text("1")
            expect(page.get_by_text("3. Температуры смешения (OA / RA / MA)", exact=True)).to_be_visible()
            expect(cursor.get_by_text("Evidence Inspector · 5 каналов · 55 отсчётов", exact=True)).to_be_visible()
            no_overflow(page)
            page.screenshot(path=screenshots / f"g4-replay-{width}.png", full_page=True)

            params = parse_qs(urlparse(page.url).query)
            event_id = params["incident_id"][0]
            direct = page.url.replace(f"timestamp={CONFIRMED.replace(':', '%3A')}", f"timestamp={MID.replace(':', '%3A')}")
            assert direct != page.url
            page.goto(direct)
            cursor.get_by_text("Evidence Inspector · 5 каналов · 55 отсчётов", exact=True).click()
            expect(cursor.get_by_text(f"ID {event_id}", exact=True)).to_be_visible()
            expect(page.get_by_text(MID, exact=True).first).to_be_visible()
            expect(page.get_by_text("DEMO_FIXTURE · G4", exact=False)).to_be_visible()
            if width == 1440:
                slider = page.get_by_role("slider")
                expect(slider).to_have_value("12")
                page.get_by_role("button", name="x5", exact=True).click()
                page.get_by_role("button", name="Воспроизведение").click()
                expect(slider).not_to_have_value("12")
                page.get_by_role("button", name="Пауза").click()
                expect(page.get_by_role("button", name="Воспроизведение")).to_be_visible()
                page.goto(direct)
                cursor.get_by_text("Evidence Inspector · 5 каналов · 55 отсчётов", exact=True).click()
                expect(cursor.get_by_text(f"ID {event_id}", exact=True)).to_be_visible()
                page.get_by_text("MA_TEMP · MEASUREMENT · 11 наблюдений", exact=True).click()
                cursor.get_by_role("button", name=BEFORE).click()
                expect(cursor.get_by_text("Ретроспектива выбранного эпизода", exact=False)).to_be_visible()
                expect(cursor.get_by_text("Нарушающие отсчёты без подтверждения", exact=True).locator("..").get_by_role("definition")).to_have_text("1")
                page.get_by_role("button", name=f"TRANSITION_HOLD · {GAP} → 2018-01-02T11:36:00").click()
                expect(page.get_by_text("Пропуск данных", exact=True)).to_be_visible()
                expect(cursor.get_by_text("Не оценено", exact=True).locator("..").get_by_role("definition")).to_have_text("1")
                expect(cursor.get_by_text(f"ID {event_id}", exact=True)).to_have_count(0)
                assert_chart_gaps(page)
                page.screenshot(path=screenshots / "g4-gap-1440.png", full_page=True)
                page.get_by_role("button", name="Инциденты · DEMO").click()
                expect(page.get_by_role("heading", name="Синтетический эпизод G4")).to_be_visible()
                assert urlparse(page.url).query == "mode=g4-demo"
                page.get_by_role("button", name="AHU Investigator").click()
                expect(page.get_by_text("DEMO_FIXTURE · синтетические исходные ряды G4", exact=True)).to_be_visible()
                assert parse_qs(urlparse(page.url).query)["dataset_id"] == ["demo-g4-mat"]
            assert not errors, errors
            page.close()
            print(f"PASS live LBNL and synthetic incident/replay/report at {width}×{height}", flush=True)
        for limit, unconfirmed, confirmed, width, height in [
            (10, "10", "0", 390, 844), (10, "10", "0", 1440, 900), (11, "0", "1", 390, 844),
        ]:
            page = browser.new_page(viewport={"width": width, "height": height})
            query = urlencode({"dataset_id": "demo-g4-mat", "start": "2018-01-02T11:05:00", "limit": limit})
            page.route("**/api/v1/investigation?*", lambda route: route.continue_(url=f"{args.url}/api/v1/investigation?{query}"))
            page.goto(f"{args.url}/incidents?mode=g4-demo")
            expect(page.get_by_text("Нарушающие отсчёты без подтверждения", exact=True).locator("..").get_by_role("definition")).to_have_text(unconfirmed)
            expect(page.get_by_text("Подтверждённые эпизоды", exact=True).locator("..").get_by_role("definition")).to_have_text(confirmed)
            no_overflow(page)
            pending = page.get_by_text("Нарушение продолжается на границе окна", exact=True)
            if limit == 10:
                expect(pending).to_be_visible()
                expect(page.get_by_text("В проверенном окне подтверждённых симптомов нет", exact=True)).to_have_count(0)
                page.screenshot(path=screenshots / f"g51-pending-{width}.png", full_page=True)
            else:
                expect(pending).to_have_count(0)
            page.close()
        print("PASS live API 10 violated observations without episode, 11 with episode", flush=True)
        if args.missing_mat_api:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.route("**/api/v1/investigation?*", lambda route: route.fulfill(response=route.fetch(
                url=f"{args.missing_mat_api}/api/v1/investigation?dataset_id=demo-g4-mat"
            )))
            page.goto(f"{args.url}/incidents?mode=g4-demo")
            expect(page.get_by_text("Правило неприменимо в этом окне", exact=True)).to_be_visible()
            page.get_by_text("Условия проверки, входы и ограничения", exact=True).click()
            expect(page.get_by_text("REQUIRED_INPUT_MISSING · 32", exact=True)).to_be_visible()
            expect(page.get_by_text("Возможные объяснения", exact=True)).to_have_count(0)
            no_overflow(page)
            page.screenshot(path=screenshots / "g41-missing-mat-390.png", full_page=True)
            page.close()
            print("PASS live missing-MAT fixture abstains without a cause", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
