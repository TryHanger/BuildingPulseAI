"""Independent preflight of actual HTTP responses and rendered participant DOM."""
import argparse
import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright

# Independent source column positions and screen headings.
COLUMNS = (47, 48, 51, 54, 64, 66, 49, 50)
HEADINGS = ["Модельные s", "SAT · K", "SAT SP · K", "MAT · K", "Fan · 0/1",
            "Cooling cmd · 0–1", "Heating cmd · 0–1", "OAT · K", "OWB · K"]
FORBIDDEN = re.compile(
    r"oracle|fault_label|ground.?truth|rubric|extra_simulated|true.value|physical_cause|"
    r"coocoival|oadamstuck|supduclea|baselinesystem|publisher|source_(?:sha|member|file)|"
    r"accepted_action|expected_cause|coordinator-only|\.csv|\b[0-9a-f]{64}\b", re.I,
)
INSTANT = {"EXCEEDS": "Превышение", "NO_ALARM": "Превышения нет", "NOT_EVALUATED": "Не оценено"}


def load_csv(raw):
    return list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline="")))


def expected(case, receipt, source_root, accepted):
    start, focus = receipt["native_window"]
    assert [start, focus, focus] == list(map(int, re.findall(r"\d+", case["native_bounds_and_focus"])))
    source = (source_root / f"g36-{receipt['profile']}" / Path(receipt["source_member"]).name).read_bytes()
    assert hashlib.sha256(source).hexdigest() == case["source_sha256"]
    rows = []
    for fields in load_csv(source)[1:]:
        time = int(Decimal(fields[0]))
        if start <= time <= focus:
            rows.append([time - focus, *(Decimal(fields[index - 1]) for index in COLUMNS)])
    trace_raw = accepted.read(receipt["trace"])
    assert hashlib.sha256(trace_raw).hexdigest() == receipt["trace_sha256"]
    traces = list(csv.DictReader(io.StringIO(trace_raw.decode())))
    window = [row for row in traces if start <= int(row["time_s"]) <= focus]
    assert [int(row["time_s"]) - focus for row in window] == [row[0] for row in rows]
    point = window[-1]
    eligible = point["basic_reason"] == "APPLICABLE"
    instant = "NOT_EVALUATED" if not eligible else "EXCEEDS" if point["basic_point_exceeds"] == "True" else "NO_ALARM"
    confirmed = point["basic_confirmed_timeline"] == "True"
    expected_state = ("NOT_EVALUATED_FAN_OFF" if not eligible else "CONFIRMED" if confirmed else
                      "POINT_EXCEEDS_NOT_CONFIRMED" if instant == "EXCEEDS" else "APPLICABLE_NO_ALARM")
    assert case["expected_status"] == expected_state
    if case["task_id"] == "T04":
        assert all(row["basic_reason"] == "APPLICABLE" and row["basic_point_exceeds"] == "False"
                   and row["basic_confirmed_timeline"] == "False" for row in window)
        clean = [row["basic_reason"] == "APPLICABLE" and row["basic_point_exceeds"] == "False"
                 and row["basic_confirmed_timeline"] == "False" for row in traces]
        first = next(i for i in range(10, len(clean)) if all(clean[i - 10:i + 1]))
        assert int(traces[first]["time_s"]) == focus
    return rows, {
        "instant": instant, "applicability": point["basic_reason"],
        "rule": "g36-sat-high@1.0.0 · >2 K · 600 s",
        "temporal": "NOT_EVALUATED" if not eligible else "CONFIRMED" if confirmed else "NOT_CONFIRMED",
        "total_ticks": len(window), "evaluated_ticks": sum(row["basic_reason"] == "APPLICABLE" for row in window),
        "missing_ticks": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    for name in ("source_root", "accepted_zip", "private", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=True, parents=True)
    with (args.private / "SOURCE_TASK_MATRIX.csv").open(encoding="utf-8") as stream:
        cases = [row for row in csv.DictReader(stream) if row["cohort"] == "CORE_G36"]
    receipts = json.loads((args.private / "STUDY_BUILD.json").read_text())["cases"]
    with ZipFile(args.accepted_zip) as accepted, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        case_decisions = {}
        for case in cases:
            case_id = case["task_id"]
            receipt = receipts[case_id]
            rows, baseline = expected(case, receipt, args.source_root, accepted)
            b_bytes = None
            for arm in "ABC":
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                observed, errors = [], []
                page.on("response", lambda response: observed.append(response))
                page.on("pageerror", lambda error: errors.append(str(error)))
                route = receipt["conditions"][arm]["route"]
                primary = page.goto(args.url + route)
                assert hashlib.sha256(primary.body()).hexdigest() == receipt["conditions"][arm]["html_sha256"]
                expect(page.locator("#signals tbody tr")).to_have_count(len(rows))
                table = page.locator("#signals")
                assert table.locator("thead th").all_text_contents() == HEADINGS
                for actual, wanted in zip(table.locator("tbody tr").all(), rows, strict=True):
                    cells = actual.locator("th,td").all_text_contents()
                    assert len(cells) == len(wanted)
                    assert all(abs(Decimal(a) - b) <= Decimal("0.0005") for a, b in zip(cells, wanted, strict=True))
                raw = page.locator("#study-data").text_content()
                payload = json.loads(raw)
                assert set(payload) == {"protocol", "panel_version", "case_id", "presentation_id", "window_seconds",
                                        "focus_seconds", "step_seconds", "channels", "points", "detector"}
                assert payload["presentation_id"] == receipt["conditions"][arm]["presentation_id"]
                assert payload["focus_seconds"] == 0 and payload["window_seconds"] == [-600, 0]
                assert [row[0] for row in payload["points"]] == [row[0] for row in rows]
                for presented, wanted in zip(payload["points"], rows, strict=True):
                    assert all(abs(Decimal(str(a)) - b) < Decimal("1e-11") for a, b in zip(presented, wanted, strict=True))
                assert payload["detector"] == ({"instant": baseline["instant"]} if arm == "A" else baseline)
                shown = page.locator("#decision dd").all_text_contents()
                assert shown[0] == INSTANT[baseline["instant"]]
                if arm == "A":
                    assert len(shown) == 1
                else:
                    expected_shown = {
                        "APPLICABLE": "Применимо", "FAN_OFF": "Вентилятор выключен",
                        "CONFIRMED": "Подтверждено", "NOT_CONFIRMED": "Не подтверждено", "NOT_EVALUATED": "Не оценено",
                    }
                    assert shown == [INSTANT[baseline["instant"]], expected_shown[baseline["applicability"]],
                                     baseline["rule"], expected_shown[baseline["temporal"]],
                                     str(baseline["total_ticks"]), str(baseline["evaluated_ticks"]), "0"]
                    detector_bytes = raw.split('"detector":', 1)[1][:-1]
                    if arm == "B":
                        b_bytes = detector_bytes
                        assert detector_bytes == (args.private / f"{case_id}-decision.json").read_text().rstrip("\n")
                        assert hashlib.sha256(detector_bytes.encode()).hexdigest() == receipt["decision_sha256"]
                    else:
                        assert detector_bytes == b_bytes
                context = page.get_by_role("complementary", name="Контекст источника")
                expect(context).to_have_count(int(arm == "C"))
                if arm == "C":
                    case_decisions[case_id] = context.inner_text()
                assert not errors
                assert {urlsplit(item.url).path for item in observed} == {route, "/study.js", "/study.css"}
                for item in observed:
                    assert item.status == 200 and urlsplit(item.url).netloc == urlsplit(args.url).netloc
                    assert not FORBIDDEN.search(item.body().decode()), item.url
                assert not FORBIDDEN.search(page.content())
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert page.locator(".table-wrap").evaluate("(el) => el.scrollWidth <= el.clientWidth")
                slider = page.get_by_role("slider")
                slider.focus()
                slider.press("Home")
                expect(page.locator("tr[aria-current=true] th")).to_have_text("-600")
                slider.press("End")
                expect(page.locator("tr[aria-current=true] th")).to_have_text("0")
                if case_id == "T04":
                    page.screenshot(path=args.output / f"g61-{arm}-1440.png", full_page=True)
                page.close()
                print(f"PASS {case_id} {arm}: exact window and DOM values, decision, units, network and no disclosure")
        assert len(set(case_decisions.values())) == 1
        page = browser.new_page(viewport={"width": 390, "height": 844}, accept_downloads=True)
        for private_route in ("/", "/coordinator-only/SOURCE_TASK_MATRIX.csv", "/%2e%2e/coordinator-only/STUDY_BUILD.json",
                              "/T04/../RUBRIC_V2.md", "/api/v1/g36-benchmark", "/SOURCE_TASK_MATRIX.csv"):
            result = page.request.get(args.url + private_route)
            assert result.status == 404 and result.text() == "Not found"
        traffic = []
        page.on("request", lambda request: traffic.append(request.url) if request.url.startswith("http") else None)
        for arm in "ABC":
            page.goto(args.url + receipts["T04"]["conditions"][arm]["route"])
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            expect(page.locator("#signals tbody tr")).to_have_count(11)
        page.clock.install()
        page.goto(args.url + receipts["T04"]["conditions"]["C"]["route"] + "?qa=1")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=args.output / "g61-C-390.png", full_page=True)
        count_before_submit = len(traffic)
        for field in page.locator("textarea").all():
            field.fill("QA_ONLY · проверка сериализации")
        page.clock.fast_forward(1000)
        page.get_by_role("button", name="Зафиксировать ответ").click()
        with page.expect_download() as event:
            page.get_by_role("button", name="Скачать обезличенный JSON").click()
        record = json.loads(event.value.path().read_text())
        assert record["collection_mode"] == "QA_ONLY" and record["status"] == "COMPLETE"
        assert len(traffic) == count_before_submit
        assert 1000 <= record["elapsed_ms"] < 180000 and "participant_id" not in record and "condition" not in record
        page.goto(args.url + receipts["T04"]["conditions"]["B"]["route"] + "?qa=1")
        page.clock.fast_forward(181000)
        expect(page.locator("#response-state")).to_have_text("Время истекло.")
        with page.expect_download() as event:
            page.get_by_role("button", name="Скачать обезличенный JSON").click()
        timeout = json.loads(event.value.path().read_text())
        assert timeout["collection_mode"] == "QA_ONLY" and timeout["status"] == "TIMEOUT"
        assert timeout["elapsed_ms"] == 180000
        print("PASS mobile layout, private paths denied, QA_ONLY complete export and clock timeout")


if __name__ == "__main__":
    main()
