"""Compare archived offline inference with real HTTP and desktop/mobile rendering."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

API = "/api/research/virtual-sensors"
FIRST_DAY = "2018-10-20"
FIELDS = ("actual", "predicted", "absolute_residual", "z", "daily_score")
CASES = ("healthy", "sa-plus-2")
TOLERANCE = 1e-9


def verify_http(api, offline):
    with urlopen(api + API) as response:
        meta = json.load(response)
    assert meta["policy_version"] == "sat-daily-coverage@1.0.0"
    assert {row["id"]: row["availability"] for row in meta["methods"]} == {
        "SAT_ONLY": "ARCHIVE_DAY_API", "SYSTEM_MAX_8": "FULL_COHORT_RESEARCH_REPORT",
        "SAT_MINUS_SETPOINT": "FULL_COHORT_RESEARCH_REPORT",
    }
    grouped = defaultdict(list)
    for row in offline:
        grouped[row["case_id"], row["timestamp"][:10]].append(row)
    maxima = dict.fromkeys(FIELDS, 0.0)
    for case in meta["cases"]:
        for day in case["days"]:
            params = urlencode({"case": case["id"], "day": day})
            with urlopen(api + API + "/day?" + params) as response:
                live = json.load(response)
            expected = grouped[case["id"], day]
            assert live["evaluated_minutes"] == len(expected)
            assert live["method"] == "SAT_ONLY" and live["running_minutes"] == len(expected)
            if not expected:
                assert live["status"] == "NOT_EVALUABLE" and live["reason"] == "NO_ELIGIBLE_MINUTES"
                continue
            assert live["status"] == "EVALUATED" and live["calendar_minutes"] == 1440
            assert abs(live["coverage"] - len(expected) / 1440) <= TOLERANCE
            assert live["alert"] == ("MODEL_ANOMALY" if float(expected[0]["daily_score"]) > 3 else None)
            for actual, original in zip(live["points"], expected, strict=True):
                assert actual["timestamp"] == original["timestamp"]
                for key in FIELDS:
                    measured = live[key] if key == "daily_score" else actual[key]
                    delta = abs(measured - float(original[key]))
                    maxima[key] = max(maxima[key], delta)
                    assert delta <= TOLERANCE, (key, delta, actual["timestamp"])
    print(f"PASS offline ↔ HTTP {len(offline)} eligible points, 14 calendar case-days, maxima {maxima}")
    return {case: grouped[case, FIRST_DAY][0] for case in CASES}, maxima


def verify_ui(web, reference, output):
    expect.set_options(timeout=15_000)
    measurements = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width, height in ((1440, 900), (390, 844)):
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(web + "/research")
            page.get_by_role("link", name="Виртуальный датчик SAT · исследование LBNL").click()
            expect(page.get_by_role("heading", name="Виртуальный датчик SAT")).to_be_visible()
            expect(page.get_by_text("RESEARCH_ONLY", exact=True)).to_be_visible()
            for case, expected in reference.items():
                page.get_by_label("Сценарий").select_option(case)
                expect(page.get_by_test_id("point-timestamp")).to_have_text(expected["timestamp"])
                for key, locator in zip(FIELDS, ("actual", "predicted", "absolute-residual", "minute-z", "daily-score"), strict=True):
                    displayed = page.get_by_test_id(locator)
                    expect(displayed).to_have_text(f"{float(expected[key]):.9f}")
                    assert abs(float(displayed.inner_text()) - float(expected[key])) <= TOLERANCE
                expect(page.get_by_test_id("research-alert")).to_have_text("Тревог нет" if case == "healthy" else "MODEL_ANOMALY")
                expect(page.get_by_test_id("coverage")).to_contain_text("955 из 1440")
                expect(page.get_by_text("PUBLISHER_BASELINE" if case == "healthy" else "UNVERIFIED_PUBLISHER_ALIAS",
                                        exact=True).first).to_be_visible()
                expect(page.get_by_role("img", name="Измерение и прогноз SAT", exact=False)).to_be_visible()
                expect(page.get_by_text("Восьмицелевой агрегированный детектор", exact=True)).to_be_visible()
                expect(page.get_by_text("Простая SAT−уставка", exact=True)).to_be_visible()
                slider = page.get_by_role("slider", name="Минута окна")
                expect(slider).to_have_attribute("aria-valuetext", expected["timestamp"])
                slider.focus()
                slider.press("ArrowRight")
                expect(page.get_by_test_id("point-timestamp")).not_to_have_text(expected["timestamp"])
                slider.press("ArrowLeft")
                expect(slider).to_have_attribute("aria-valuetext", expected["timestamp"])
                measurements[f"{width}-{case}"] = expected["timestamp"]
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                if (width, case) in {(1440, "sa-plus-2"), (390, "healthy")}:
                    page.evaluate("window.scrollTo(0, 0)")
                    page.screenshot(path=output / f"virtual-sensor-{case}-{width}.png", full_page=True)
            page.get_by_label("Дата источника").select_option("2018-10-22")
            expect(page.get_by_test_id("research-alert")).to_have_text("NOT_EVALUABLE")
            expect(page.get_by_text("NO_ELIGIBLE_MINUTES", exact=True)).to_be_visible()
            assert not errors, errors
            page.close()
            print(f"PASS UI ↔ HTTP ↔ offline at {width}×{height}, both controls and no-coverage day")
        browser.close()
    return measurements


def main(api, web, offline, output):
    output.mkdir(parents=True, exist_ok=True)
    with offline.open() as stream:
        rows = list(csv.DictReader(stream))
    reference, maxima = verify_http(api, rows)
    ui = verify_ui(web, reference, output)
    receipt = {"status": "PASS", "absolute_tolerance": TOLERANCE, "http_points": len(rows),
               "maximum_absolute_http_delta": maxima, "ui_timestamps": ui, "reference": reference}
    (output / "SAT_PARITY.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", required=True)
    parser.add_argument("--web", required=True)
    parser.add_argument("--offline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(**vars(parser.parse_args()))
