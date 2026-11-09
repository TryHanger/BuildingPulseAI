"""Browser acceptance checks against running scratch FastAPI and Vite."""
import argparse
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5180")
    parser.add_argument("--output", type=Path, default=Path("handoff/screenshots"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        print(f"Chromium {browser.version}")
        for width, height in ((1440, 900), (1280, 800), (1024, 768), (390, 844)):
            page = browser.new_page(viewport={"width": width, "height": height}, timezone_id="Asia/Qyzylorda")
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(args.url)
            expect(page.get_by_role("heading", name="AHU Investigator")).to_be_visible()
            expect(page.get_by_text("VERIFIED_RUNTIME", exact=True)).to_be_visible()
            expect(page.get_by_text("SOURCE_SIMULATION_TIME", exact=False)).to_be_visible()
            expect(page.get_by_text("2018-01-01T01:00:00", exact=True)).to_have_count(2)
            expect(page.get_by_text("2018-01-01 01:00:00 UTC", exact=True)).to_have_count(0)
            expect(page.get_by_text("NOT_EVALUABLE", exact=True)).to_be_visible()
            expect(page.get_by_text("NOT_ASSESSED", exact=True)).to_be_visible()
            expect(page.get_by_text("UNEXPLAINED", exact=True)).to_have_count(0)
            pressure = page.locator('svg [aria-label="Исходные значения давления"]')
            expect(pressure).to_contain_text("SA_SP · raw 402.07953")
            expect(pressure).to_contain_text("SA_SPSPT · raw 1.60746")
            expect(pressure).to_contain_text("единицы не проверены")
            assert pressure.evaluate("""group => {
              const bounds = group.getBoundingClientRect();
              const container = group.closest('svg').parentElement.getBoundingClientRect();
              return bounds.left >= container.left && bounds.right <= container.right;
            }"""), "SVG pressure warning is clipped"
            expect(page.get_by_text("SA_SP · BASIC · raw 402.07953 · Единица не проверена", exact=True)).to_be_visible()
            expect(page.get_by_text("SA_SPSPT · BASIC · raw 1.60746 · Единица не проверена", exact=True)).to_be_visible()
            expect(page.get_by_text("inH2O", exact=False)).to_have_count(0)
            expect(page.get_by_text("PAIR_NOT_VERIFIED", exact=False)).to_be_visible()
            expect(page.get_by_role("button", name="Наложение недоступно")).to_be_disabled()
            expect(page.get_by_text("CHWC_VLV_DM", exact=True)).to_be_visible()
            expect(page.get_by_text("CHWC_VLV", exact=True)).to_have_count(0)
            expect(page.locator("canvas")).to_have_count(3)
            expect(page.get_by_role("region", name="Сегменты режима")).to_be_visible()
            expect(page.get_by_text("Качество данных · канонические сигналы", exact=True)).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Page overflows viewport"
            assert not errors, errors
            page.screenshot(path=args.output / f"investigator-{width}x{height}.png", full_page=True)
            print(f"PASS live source {width}x{height}")
            if width == 1440:
                dataset = page.get_by_label("Датасет")
                annual_labels = dataset.locator("option").all_text_contents()
                annual_labels = [label for label in annual_labels if label.startswith("AHU_annual.csv")]
                assert len(annual_labels) == 3 and len(set(annual_labels)) == 3
                dataset.select_option("ds_8e5b1ddfdd14")
                seek = page.get_by_label("Время источника")
                seek.fill("2018-12-31T23:59:00Z")
                page.get_by_role("button", name="Перейти ко времени").click()
                expect(page.get_by_role("alert")).to_contain_text("формате 2018-MM-DDTHH:MM:SS")
                seek.fill("2018-12-31T23:59:00")
                page.get_by_role("button", name="Перейти ко времени").click()
                expect(page.get_by_text("2018-12-31T23:59:00", exact=True)).to_have_count(2)
                expect(page.get_by_text("Отсчётов в окне · 1")).to_be_visible()
                expect(page.get_by_role("button", name="Следующее окно")).to_be_disabled()
                page.screenshot(path=args.output / "annual-direct-seek.png", full_page=True)
                seek.fill("2018-01-09T06:02:00")
                page.get_by_role("button", name="Перейти ко времени").click()
                expect(page.get_by_text("CHWC_VLV_DM · BASIC · 1.000 fraction", exact=True)).to_be_visible()
                expect(page.get_by_text("NOT_DETECTED_IN_EVALUATED_TESTS", exact=True)).to_be_visible()
                expect(page.get_by_text("NOT_ASSESSED", exact=True)).to_be_visible()
                expect(page.get_by_text("SIGNAL_RANGE_VIOLATION", exact=True)).to_have_count(0)
                page.screenshot(path=args.output / "valid-saturated-command.png", full_page=True)
                seek.fill("2018-07-03T12:00:00")
                page.get_by_role("button", name="Перейти ко времени").click()
                expect(page.get_by_text("Устойчивый статус ON", exact=True)).to_be_visible()
                expect(page.get_by_role("region", name="Проверки источника").get_by_text("COOLING_ENABLE_UNOBSERVED", exact=False)).to_be_visible()
                expect(page.get_by_text("PANEL_EXCLUDES_SIGNAL", exact=False)).to_be_visible()
                expect(page.get_by_role("region", name="Сегменты режима").locator('button[aria-current="true"]')).to_have_attribute(
                    "aria-label", re.compile(r"^RUNNING · 2018-07-03T12:00:00")
                )
                page.screenshot(path=args.output / "g2-midyear-running.png", full_page=True)
                dataset.select_option("ds_69a163ff26f9")
                seek = page.get_by_label("Время источника")
                seek.fill("2018-01-02T06:01:00")
                page.get_by_role("button", name="Перейти ко времени").click()
                expect(page.get_by_text("Удержание после пуска", exact=True)).to_be_visible()
                expect(page.get_by_text("sat-tracking · INAPPLICABLE · FAN_TRANSITION_HOLD", exact=True)).to_be_visible()
                page.screenshot(path=args.output / "g2-startup-hold.png", full_page=True)
                timeline = page.get_by_role("region", name="Сегменты режима")
                timeline.get_by_role("button", name=re.compile(r"^RUNNING ·")).first.click()
                expect(page.get_by_role("region", name="Проверки источника").get_by_text("COOLING_ENABLE_UNOBSERVED", exact=False)).to_be_visible()
                print("PASS live G2 mode, startup hold, midyear seek and segment timeline click")
                seek.fill("2018-01-01T01:00:00")
                page.get_by_role("button", name="Перейти ко времени").click()
                page.get_by_label("Панель").select_option("EXTRA")
                expect(page.get_by_text("CHWC_VLV", exact=True)).to_be_visible()
                expect(page.get_by_text("CHWC_VLV (положение модели):", exact=True)).to_be_visible()
                expect(page.get_by_text("SYS_CTL", exact=True)).to_have_count(0)
                page.get_by_role("button", name="Следующее окно").click()
                expect(page.get_by_text("2018-01-01T09:00:00", exact=True)).to_have_count(2)
                expect(page.get_by_text("VERIFIED_RUNTIME", exact=True)).to_be_visible()
                page.get_by_role("button", name="Предыдущее окно").click()
                expect(page.get_by_text("2018-01-01T01:00:00", exact=True)).to_have_count(2)
                page.get_by_role("button", name="Воспроизведение", exact=True).click()
                expect(page.get_by_text("2018-01-01T01:00:00", exact=True)).to_have_count(0)
                page.get_by_role("button", name="Пауза", exact=True).click()
                page.get_by_label("Источник данных").select_option("DEMO_FIXTURE")
                expect(page.get_by_text("DEMO_FIXTURE · UI_MOCK_V0", exact=False)).to_be_visible()
                page.get_by_role("button", name="Инциденты · DEMO", exact=False).click()
                expect(page.get_by_text("DEMO_FIXTURE · UI_MOCK_V0", exact=False)).to_be_visible()
                assert not errors, errors
                print("PASS EXTRA, pagination, replay and explicit demo incident navigation")
            page.close()

        page = browser.new_page()
        page.route("**/api/v1/datasets?*", lambda route: route.fulfill(status=503, json={
            "detail": {"code": "AUDIT_UNAVAILABLE", "message": "Injected failure"}
        }))
        page.goto(args.url)
        expect(page.get_by_role("alert")).to_contain_text("HTTP 503")
        expect(page.get_by_text("VERIFIED_RUNTIME", exact=True)).to_have_count(0)
        expect(page.get_by_text("DEMO_FIXTURE · UI_MOCK_V0", exact=False)).to_have_count(0)
        expect(page.locator("canvas")).to_have_count(0)
        page.close()
        print("PASS HTTP 503 stays visible without fixture fallback")

        def gap_window(route):
            response = route.fetch()
            data = response.json()
            data["timestamps"] = ["2018-01-01T01:00:00", "2018-01-01T01:05:00", "2018-01-01T10:05:00"]
            data["gap_before"] = [False, False, True]
            data["sample_seconds"] = 300  # Synthetic chart input, independent of the LBNL minute grid.
            for signal in data["signals"]:
                signal["values"] = signal["values"][:3]
                if signal["canonical_id"] == "SA_TEMPSPT":
                    signal.update(availability="UNAVAILABLE", values=[None] * 3)
            route.fulfill(response=response, json=data)

        page = browser.new_page()
        page.route("**/api/v1/series?*", gap_window)
        page.goto(args.url)
        expect(page.get_by_text("VERIFIED_RUNTIME", exact=True)).to_be_visible()
        expect(page.get_by_text("CHWC_VLV_DM · BASIC · 0.000 fraction", exact=True)).to_be_visible()
        expect(page.get_by_text("SA_TEMPSPT · BASIC · UNAVAILABLE", exact=True)).to_be_visible()
        page.locator('input[type="range"]').press("End")
        expect(page.get_by_text("Пропуск данных", exact=True)).to_be_visible()
        expect(page.locator("canvas")).to_have_count(3)
        geometry = page.evaluate("""async () => {
          const module = performance.getEntriesByType('resource').find(({ name }) =>
            new URL(name).pathname.endsWith('/echarts.js'));
          const echarts = await import(module.name);
          const host = document.querySelector('[_echarts_instance_]');
          const chart = echarts.getInstanceByDom(host);
          const { xAxis, series } = chart.getOption();
          const pixel = value => chart.convertToPixel({ xAxisIndex: 0 }, value);
          return {
            axis: xAxis[0].type,
            points: series[0].data,
            connectsNull: series[0].connectNulls,
            ratio: (pixel(32700) - pixel(300)) / (pixel(300) - pixel(0))
          };
        }""")
        assert geometry["axis"] == "value" and not geometry["connectsNull"], geometry
        assert [point[0] for point in geometry["points"]] == [0, 300, 16500, 32700], geometry
        assert geometry["points"][2][1] is None, geometry
        assert abs(geometry["ratio"] - 108) < 1e-7, geometry
        page.screenshot(path=args.output / "elapsed-nine-hour-gap.png", full_page=True)
        page.close()
        print(f"PASS zero, null and nine-hour gap, measured ECharts pixel ratio {geometry['ratio']:.1f}")

        def encoding_violation(route):
            response = route.fetch()
            data = response.json()
            data.update(anomaly_status="DETECTED", display_state="ALARM", cause_status="NOT_ASSESSED",
                        issue_class="SIGNAL_RANGE_VIOLATION", mode="TRANSITION_HOLD", fan_on=True)
            for signal in data["signal_quality"]:
                if signal["canonical_id"] == "CHWC_VLV_DM":
                    signal["flags"] = ["COMMAND_OUT_OF_RANGE"]
            data["methods"][0].update(method_status="APPLICABLE", predicate="VIOLATED",
                                      reason_code="COMMAND_FRACTION_RANGE")
            for root in data["methods"][0]["roots"]:
                root["value"] = 1.5 if root["canonical_id"] == "CHWC_VLV_DM" else 1
            route.fulfill(response=response, json=data)

        def invalid_command_sample(route):
            response = route.fetch()
            data = response.json()
            for signal in data["signals"]:
                if signal["canonical_id"] == "CHWC_VLV_DM":
                    signal["values"][0] = 1.5
                if signal["canonical_id"] == "SF_SPD_DM":
                    signal["values"][0] = 1
            route.fulfill(response=response, json=data)

        page = browser.new_page()
        page.route("**/api/v1/diagnostics?*", encoding_violation)
        page.route("**/api/v1/series?*", invalid_command_sample)
        page.goto(args.url)
        expect(page.get_by_text("SIGNAL_RANGE_VIOLATION", exact=True)).to_be_visible()
        expect(page.get_by_text("CHWC_VLV_DM · BASIC · 1.500 fraction", exact=False)).to_be_visible()
        expect(page.get_by_text("DETECTED", exact=True)).to_be_visible()
        expect(page.get_by_text("Команда вне [0, 1]", exact=True)).to_be_visible()
        expect(page.get_by_text("NOT_ASSESSED", exact=True)).to_be_visible()
        expect(page.get_by_text("CONFIRMED", exact=True)).to_have_count(0)
        expect(page.get_by_text("Нарушение кодирования команды управления.", exact=False)).to_be_visible()
        page.screenshot(path=args.output / "encoding-violation.png", full_page=True)
        page.close()
        print("PASS injected signal encoding violation has no assessed or confirmed cause")

        def empty_window(route):
            response = route.fetch()
            data = response.json()
            data.update(timestamps=[], gap_before=[], next_start=None)
            for signal in data["signals"]:
                signal["values"] = []
            route.fulfill(response=response, json=data)

        page = browser.new_page()
        page.route("**/api/v1/series?*", empty_window)
        page.goto(args.url)
        expect(page.get_by_text("В этом окне нет отсчётов.")).to_be_visible()
        expect(page.locator("canvas")).to_have_count(0)
        page.close()
        print("PASS empty window")

        page = browser.new_page()
        page.route("**/api/v1/modes?*", lambda route: route.fulfill(status=503, json={
            "detail": {"code": "MODES_TEST_UNAVAILABLE", "message": "Injected modes endpoint failure"}
        }))
        page.goto(args.url)
        expect(page.get_by_role("alert")).to_contain_text("MODES_TEST_UNAVAILABLE")
        expect(page.get_by_text("VERIFIED_RUNTIME", exact=True)).to_be_visible()
        expect(page.locator("canvas")).to_have_count(3)
        expect(page.get_by_role("region", name="Сегменты режима")).to_have_count(0)
        page.close()
        print("PASS modes failure leaves telemetry and point diagnostics visible")
        browser.close()


if __name__ == "__main__":
    main()
