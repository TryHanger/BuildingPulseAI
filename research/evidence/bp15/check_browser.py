"""Compare the running Investigator with accepted source artifacts, outside its API adapters."""
import argparse
import csv
import gzip
import io
import json
import math
from hashlib import sha256
from pathlib import Path
from statistics import mean

import numpy as np
import pandas as pd
from lightgbm import Booster
from playwright.sync_api import expect, sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE06 = HERE.parent / "archive_bp_ml_transfer_normal_06"
FIELD = HERE.parent / "field_native_09/observed"
REGISTRY = ROOT / "research/ml_repro_02/registry"
MEMBER = "78878e54e682a76622c2305f329481f3b5397a61b347f3a783f947a4b9b9d7a4"
CHANNELS = ("supply", "exhaust", "heat_request", "cool_request")
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def rows(path):
    return list(csv.DictReader(path.read_text().splitlines()))


def pinned(path, expected_sha):
    payload = path.read_bytes()
    assert sha256(payload).hexdigest() == expected_sha, path
    return payload


def sample(page, time, values):
    page.get_by_label("Отсчёт источника").select_option(label=str(time))
    for index, expected in enumerate(values):
        shown = page.get_by_test_id(f"sample-value-{index}").inner_text()
        if expected is None:
            assert shown == "MISSING"
        else:
            assert math.isclose(float(shown), expected, rel_tol=1e-12, abs_tol=1e-12)


def inspect_case(page, screenshot, anomaly, *digests):
    expect(page.get_by_test_id("anomaly")).to_have_text(anomaly)
    expect(page.get_by_test_id("cause")).to_have_text("ABSTAIN")
    for key in ("support", "conflict", "missing", "action", "quality", "applicability"):
        expect(page.get_by_test_id(key)).not_to_be_empty()
    page.get_by_text("Источник, версии и контрольные суммы").click()
    assert page.get_by_role("link", name="Запись издателя").get_attribute("href").startswith("https://")
    for digest in digests:
        expect(page.get_by_text(digest, exact=True)).to_be_visible()
    page.screenshot(path=screenshot, full_page=True, animations="disabled")
    page.get_by_role("button", name="Только сигнал").click()
    expect(page.get_by_test_id("anomaly")).to_have_text(anomaly)
    for key in ("support", "cause", "action"):
        expect(page.get_by_test_id(key)).to_have_count(0)
    page.get_by_role("button", name="Свидетельства и действие").click()


def verify_a(page, screenshots):
    manifest = json.loads(pinned(
        REGISTRY / "MODEL_ARTIFACT_MANIFEST.json",
        "359afbe1d3022e64c52ec5e1d916bb731a8c4c45aef9a835d0c9ab6ba73c0734",
    ))
    window = manifest["windows"]["sa-plus-2"]
    model = manifest["models"]["SA_TEMP"]
    assert window["member_sha256"] == MEMBER and window["alias_status"] == "UNVERIFIED_PUBLISHER_ALIAS"
    frame = pd.read_parquet(io.BytesIO(pinned(REGISTRY / window["file"], window["sha256"])))
    day = frame[frame.timestamp.dt.strftime("%Y-%m-%d").eq("2018-10-20")].copy()
    day = day[day.eligible & np.isfinite(day[manifest["schema"]["available_channels"]]).all(axis=1)].copy()
    day["hour"] = day.timestamp.dt.hour
    day["month"] = day.timestamp.dt.month
    day["day_of_week"] = day.timestamp.dt.dayofweek
    booster = Booster(model_str=pinned(REGISTRY / model["file"], model["sha256"]).decode())
    predicted = booster.predict(day[model["feature_order"]], num_threads=1)
    expected_score = mean((abs(day.SA_TEMP.to_numpy() - predicted) - model["abs_center"]) / model["abs_scale"])
    assert len(day) == 955 and expected_score > 3
    expect(page.get_by_test_id("quality")).to_contain_text(f"{len(day)} / 1440")
    expect(page.get_by_test_id("support")).to_contain_text(f"{expected_score:.4f}")
    expect(page.get_by_test_id("conflict")).to_contain_text("UNAVAILABLE")
    expect(page.get_by_test_id("conflict")).to_contain_text("UNVERIFIED_PUBLISHER_ALIAS")
    expect(page.locator("#bp15-sample option")).to_have_count(len(day))
    assert page.locator("#bp15-sample option").all_text_contents() == day.timestamp.astype(str).tolist()
    for index in (0, len(day) // 2, len(day) - 1):
        tick = day.iloc[index]
        sample(page, tick.timestamp, [tick.SA_TEMP, predicted[index]])
    wire = page.request.get("/api/research/virtual-sensors/day?case=sa-plus-2&day=2018-10-20")
    assert wire.ok
    delivered = wire.json()["points"]
    assert [point["timestamp"] for point in delivered] == day.timestamp.astype(str).tolist()
    np.testing.assert_allclose([point["actual"] for point in delivered], day.SA_TEMP, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose([point["predicted"] for point in delivered], predicted, rtol=1e-12, atol=1e-12)
    inspect_case(page, screenshots / "A-lbnl.png", "MODEL_ANOMALY", MEMBER, manifest["source_sha256"])
    return {"evaluated_minutes": len(day), "daily_z": expected_score, "source_identity": "UNAVAILABLE"}


def verify_b(page, screenshots):
    receipt = json.loads((STAGE06 / "TARGET_NORMAL_06_RECEIPT.json").read_bytes())
    trace_name = "TARGET_NORMAL_06_MINUTE_TRACE.csv.gz"
    blocks_name = "TARGET_NORMAL_06_BLOCKS.csv"
    trace = pinned(HERE / "accepted" / trace_name, receipt["artifacts"][trace_name])
    window = [point for point in csv.DictReader(gzip.decompress(trace).decode().splitlines())
              if 17645700 <= int(point["model_seconds"]) < 17649300]
    blocks = list(csv.DictReader(pinned(STAGE06 / blocks_name, receipt["artifacts"][blocks_name]).decode().splitlines()))
    assert len(window) == 60
    page.get_by_role("button", name="B · G36").click()
    expect(page.get_by_test_id("applicability")).to_contain_text(receipt["gate"])
    expect(page.get_by_test_id("quality")).to_contain_text(f'{receipt["eligible_minutes"]} / {receipt["calendar_minutes"]}')
    expect(page.get_by_test_id("support")).to_contain_text("7 / 7")
    expect(page.get_by_test_id("conflict")).to_contain_text("55.184006")
    assert page.locator("#bp15-sample option").all_text_contents() == [point["model_seconds"] for point in window]
    for point in window:
        prediction = point["LIGHTGBM_SOURCE_TRAINED_PREDICTION_degF"]
        sample(page, point["model_seconds"], [
            float(point["SAT_MEASURED_SIMULATED_BAS_degF"]), float(point["ACTIVE_SAT_SETPOINT_degF"]),
            float(prediction) if prediction else None,
        ])
        expect(page.get_by_test_id("sample-context")).to_contain_text(
            "ELIGIBLE" if point["ELIGIBLE"] == "True" else point["ABSTAIN_REASON"])
    actual = [row.inner_text().split() for row in page.locator("tbody tr").all()]
    assert len(actual) == len(blocks) == 7
    for (block, start, z, decision), expected in zip(actual, blocks, strict=True):
        assert (block, start, decision) == (expected["block"], expected["start_model_s"], expected["lightgbm_reduced_decision"])
        assert math.isclose(float(z), float(expected["lightgbm_reduced_z"]), rel_tol=1e-12)
    sample(page, 17647500, [
        float(window[30]["SAT_MEASURED_SIMULATED_BAS_degF"]),
        float(window[30]["ACTIVE_SAT_SETPOINT_degF"]),
        float(window[30]["LIGHTGBM_SOURCE_TRAINED_PREDICTION_degF"]),
    ])
    inspect_case(page, screenshots / "B-g36.png", "ABSTAIN", receipt["artifacts"][trace_name],
                 receipt["artifacts"][blocks_name], receipt["sha256"]["BaselineSystem.csv"])
    return {"minutes_compared": len(window), "blocks_compared": len(blocks), "gate": receipt["gate"]}


def verify_field(page, screenshots, case, ahu):
    outcome = next(row for row in rows(FIELD / "EVENT_OUTCOMES.csv") if row["ahu"] == ahu)
    trace = list(csv.DictReader(pinned(FIELD / outcome["trace"], outcome["trace_sha256"]).decode().splitlines()))
    page.get_by_role("button", name=f"{case} · Mendeley · {ahu}").click()
    expect(page.get_by_test_id("anomaly")).to_have_text(outcome["A_change"])
    expect(page.get_by_test_id("cause")).to_have_text(outcome["physical_fault"])
    expect(page.get_by_test_id("applicability")).to_contain_text(f'A: {outcome["A_status"]} · B: {outcome["B_status"]}')
    assert page.locator("#bp15-sample option").all_text_contents() == [point["native_time"] for point in trace]
    for point in trace:
        sample(page, point["native_time"], [int(point[key]) if point[key] else None for key in CHANNELS])
        expect(page.get_by_test_id("sample-context")).to_have_text(point["partition"])
    if case == "C":
        expect(page.get_by_test_id("support")).to_contain_text(outcome["A_first_off_inclusive"])
        expect(page.get_by_test_id("support")).to_contain_text(outcome["A_confirm_off"])
        expect(page.get_by_test_id("conflict")).to_contain_text(outcome["B_change"])
        expect(page.get_by_test_id("conflict")).to_contain_text(f'{outcome["pair_01_ticks"]} отсчётов')
        sample(page, outcome["A_first_off_inclusive"], [0, 1, 1, 0])
    else:
        assert all(not point[key] for point in trace for key in CHANNELS)
        expect(page.get_by_text("Нет значений для графика. Пропуски сохранены.")).to_be_visible()
        expect(page.get_by_test_id("quality")).to_contain_text("приток 0, вытяжка 0, нагрев 0, охлаждение 0")
        expect(page.get_by_test_id("action")).to_contain_text("независимый расход")
        sample(page, next(point["native_time"] for point in trace if point["partition"] == "WINDOW"), [None] * 4)
    inspect_case(page, screenshots / f"{case}-{ahu}.png", outcome["A_change"],
                 outcome["trace_sha256"], outcome["raw_sha256"])
    return {"samples_compared": len(trace), "rule_a": outcome["A_change"], "rule_b": outcome["B_change"],
            "physical_fault": outcome["physical_fault"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:15195")
    parser.add_argument("--screenshots", type=Path, required=True)
    args = parser.parse_args()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(base_url=args.url, viewport={"width": 1366, "height": 900}, device_scale_factor=1)
        errors, writes = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: writes.append(request.url) if request.method in WRITE_METHODS else None)
        page.goto(args.url + "/assets/ahu-sd")
        page.get_by_role("link", name="От сигнала к проверке · BP-15").click()
        expect(page.get_by_text("BP-15 · RESEARCH_ONLY")).to_be_visible()
        report = {
            "A": verify_a(page, args.screenshots),
            "B": verify_b(page, args.screenshots),
            "C": verify_field(page, args.screenshots, "C", "AHU23"),
            "D": verify_field(page, args.screenshots, "D", "AHU2"),
        }
        page.get_by_role("button", name="C · Mendeley").click()
        expect(page.get_by_test_id("anomaly")).to_have_text("BAS_ON_TO_OFF_OBSERVED")
        page.get_by_role("button", name="Только сигнал").click()
        page.screenshot(path=args.screenshots / "C-signal-only.png", full_page=True, animations="disabled")
        page.get_by_role("button", name="Свидетельства и действие").click()

        page.route("**/api/research/transfer-trace-15", lambda route: route.fulfill(status=503))
        page.get_by_role("button", name="B · G36").click()
        expect(page.get_by_role("alert")).to_contain_text("UNAVAILABLE")
        expect(page.get_by_test_id("anomaly")).to_have_count(0)
        expect(page.locator("#bp15-sample")).to_have_count(0)
        page.route("**/api/research/virtual-sensors/day?*", lambda route: route.fulfill(status=503))
        page.get_by_role("button", name="A · LBNL").click()
        expect(page.get_by_role("alert")).to_contain_text("UNAVAILABLE")
        page.route("**/api/research/field-evidence", lambda route: route.fulfill(status=200, json={"cases": []}))
        page.get_by_role("button", name="D · Mendeley").click()
        expect(page.get_by_role("alert")).to_contain_text("UNAVAILABLE")
        assert not errors and not writes, (errors, writes)
        report["negative"] = {"missing_stage02": "PASS", "missing_stage06": "PASS",
                              "malformed_stage10": "PASS", "stale_display": "PASS", "writes": 0, "page_errors": 0}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        browser.close()


if __name__ == "__main__":
    main()
