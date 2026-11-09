"""Exercise the local participant screen without storing any test submissions."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from pilot_data import ANOMALY, BASELINE, PROTOCOL, score, tasks

ROUTE = "/research/engineer-decision-pilot"
API = "/api/research/"
CLOCK = """
window.pilotTestClock = 0;
window.pilotTestHidden = false;
Object.defineProperty(performance, 'now', {value: () => window.pilotTestClock});
Object.defineProperty(document, 'hidden', {get: () => window.pilotTestHidden});
"""


def by_button(page, name):
    return page.get_by_role("button", name=name, exact=True)


def open_task(page, case, position):
    expect(page.get_by_role("heading", name=f"Задание {position} из 4", exact=True)).to_be_visible()
    expect(page.get_by_test_id("stimulus")).to_have_count(0)
    expect(page.locator("form")).to_have_count(0)
    by_button(page, "Открыть задание").click()
    expect(page.get_by_role("heading", name=f"Случай {case}", exact=True)).to_be_visible(timeout=30000)
    return page.get_by_test_id("stimulus")


def test_sequence(browser, url, sequence, screenshots):
    page = browser.new_page(viewport={"width": 1366, "height": 900}, accept_downloads=True)
    page.add_init_script(CLOCK)
    requests, errors, expected = [], [], []
    page.on("request", lambda req: requests.append((req.method, req.url)))
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.goto(f"{url}{ROUTE}?sequence={sequence}")
    if sequence == 1:
        expect(by_button(page, "Начать сессию")).to_be_visible()
        page.screenshot(path=screenshots / "00-intro.png", full_page=True, animations="disabled")
    by_button(page, "Начать сессию").click()
    seen = {}
    for position, (case, condition) in enumerate(tasks(sequence), 1):
        page.evaluate("(now) => {window.pilotTestClock = now}", position * 10000)
        stimulus = open_task(page, case, position)
        expect(stimulus).to_have_attribute("data-condition", condition)
        expect(stimulus.get_by_test_id("anomaly")).to_have_text(ANOMALY[case])
        expect(stimulus.get_by_test_id("action")).to_have_count(0)
        expect(page.get_by_role("link")).to_have_count(0)
        expect(page.locator("input:checked")).to_have_count(0)
        expect(page.get_by_role("radio")).to_have_count(12)
        expect(page.get_by_role("textbox")).to_have_count(0)
        assert not page.locator("[data-correct], [data-answer-key]").count()
        assert "STOP_OOD_HEALTHY" not in stimulus.inner_text()
        labels = page.locator("fieldset label").all_text_contents()
        assert all(label.strip() not in stimulus.inner_text() for label in labels)
        seen[case] = (condition, tuple(labels))
        if condition == "evidence-to-action":
            expect(stimulus.get_by_test_id("cause")).to_have_text("ABSTAIN")
            expect(stimulus.get_by_role("heading", name="Нативная телеметрия")).to_be_visible()
            expect(stimulus.locator("#bp15-sample option")).to_have_count({"A": 955, "B": 60, "C": 20, "D": 20}[case])
            if case == "A":
                expect(stimulus).to_contain_text("UNVERIFIED_PUBLISHER_ALIAS")
            if case == "B":
                expect(stimulus.locator("tbody tr")).to_have_count(7)
            if case == "C":
                stimulus.get_by_label("Отсчёт источника").select_option(label="2019-03-01 13:45:00")
                expect(stimulus.get_by_test_id("sample-value-0")).to_have_text("0")
                expect(stimulus.get_by_test_id("sample-value-1")).to_have_text("1")
            if case == "D":
                for channel in range(4):
                    expect(stimulus.get_by_test_id(f"sample-value-{channel}")).to_have_text("MISSING")
        else:
            expect(stimulus.get_by_test_id("cause")).to_have_count(0)
            expect(stimulus.get_by_role("heading", name="Нативная телеметрия")).to_have_count(0)

        if case == "C" and sequence in (1, 2):
            page.screenshot(path=screenshots / f"case-c-{condition}.png", full_page=True, animations="disabled")
        submit = by_button(page, "Подтвердить ответы")
        expect(submit).to_be_disabled()
        expect(by_button(page, "Сохранить ответы")).to_have_count(0)
        choices = {"decision": 1, "inference": 2, "measurement": 3}
        for question, option in choices.items():
            page.locator(f'input[name="{question}"][value="{option}"]').check()
        interrupted = sequence == 1 and position == 2
        if interrupted:
            page.evaluate("""() => {
                window.pilotTestHidden = true;
                document.dispatchEvent(new Event('visibilitychange'));
                window.pilotTestHidden = false;
                document.dispatchEvent(new Event('visibilitychange'));
            }""")
        elapsed = 1200 + position * 25
        page.evaluate("(now) => {window.pilotTestClock = now}", position * 10000 + elapsed)
        submit.click()
        expected.append({
            "case_id": case, "condition": condition, "position": position, "anomaly": ANOMALY[case],
            "choices": choices, "elapsed_ms": elapsed, "interrupted": interrupted,
        })

    expect(page.get_by_role("heading", name="Четыре задания завершены")).to_be_visible()
    with page.expect_download() as download:
        by_button(page, "Сохранить ответы").click()
    record = json.loads(download.value.path().read_text())
    assert record["responses"] == expected
    assert record["protocol"] == PROTOCOL and record["baseline"] == BASELINE
    assert record["sequence"] == sequence
    assert download.value.suggested_filename == f'bp16-response-{record["session_id"]}.json'
    checked = score(record)
    assert len(checked["tasks"]) == 4
    assert checked["tasks"][1]["include_in_timing_summary"] is (sequence != 1)
    assert all(method == "GET" for method, _ in requests)
    assert all(url.split("/api", 1)[1].startswith("/research/") for _, url in requests if "/api/" in url)
    assert page.evaluate("localStorage.length + sessionStorage.length") == 0
    assert not errors, errors
    page.close()
    return seen


def check_fail_closed(browser, url, default_url):
    page = browser.new_page()
    page.goto(f"{default_url}{ROUTE}?sequence=1")
    expect(page.get_by_role("alert")).to_have_text("Исследовательский сеанс недоступен.")
    for suffix in ("", "?sequence=9", "?sequence=1&sequence=2"):
        page.goto(f"{url}{ROUTE}{suffix}")
        expect(page.get_by_role("alert")).to_contain_text("Нужен корректный код назначения")
        expect(by_button(page, "Начать сессию")).to_have_count(0)

    page.goto(f"{url}{ROUTE}?sequence=1")
    page.route(f"**{API}virtual-sensors/day?*", lambda route: route.fulfill(status=503))
    by_button(page, "Начать сессию").click()
    by_button(page, "Открыть задание").click()
    expect(page.get_by_role("alert")).to_contain_text("UNAVAILABLE")
    expect(page.get_by_role("radio")).to_have_count(0)
    expect(by_button(page, "Сохранить ответы")).to_have_count(0)
    page.once("dialog", lambda dialog: dialog.accept())
    by_button(page, "Прервать сессию").click()
    expect(page.get_by_role("status")).to_contain_text("Сессия прервана")
    page.close()


def check_loading_clock(browser, url):
    page = browser.new_page()
    page.add_init_script(CLOCK)
    page.goto(f"{url}{ROUTE}?sequence=1")
    by_button(page, "Начать сессию").click()

    def delay(route):
        page.evaluate("window.pilotTestClock = 60000")
        route.continue_()

    page.route(f"**{API}virtual-sensors/day?*", delay)
    for case, position in zip(("A", "B", "D", "C"), range(1, 5), strict=True):
        open_task(page, case, position)
        for name in ("decision", "inference", "measurement"):
            page.locator(f'input[name="{name}"][value="1"]').check()
        page.evaluate("window.pilotTestClock += 1000")
        by_button(page, "Подтвердить ответы").click()
    with page.expect_download() as download:
        by_button(page, "Сохранить ответы").click()
    record = json.loads(download.value.path().read_text())
    assert [row["elapsed_ms"] for row in record["responses"]] == [1000] * 4
    page.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--default-url", required=True)
    parser.add_argument("--screenshots", required=True, type=Path)
    args = parser.parse_args()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    pairs = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        check_fail_closed(browser, args.url, args.default_url)
        check_loading_clock(browser, args.url)
        for code in range(1, 9):
            for case, (condition, labels) in test_sequence(browser, args.url, code, args.screenshots).items():
                if (case, condition) in pairs:
                    assert pairs[case, condition] == labels
                pairs[case, condition] = labels
        assert len(pairs) == 8
        for case in ANOMALY:
            assert pairs[case, "signal-only"] == pairs[case, "evidence-to-action"]
        browser.close()
    print(json.dumps({
        "assignment_sequences_checked": 8, "case_condition_pairs": 8, "stimulus_displays": 32,
        "choice_labels_and_status_match": True, "key_or_prefilled_answer_in_stimulus": False,
        "loading_excluded_and_visibility_flagged": True, "local_download_and_offline_scoring": True,
        "default_build_disabled": True, "wrong_code_and_source_failure_blocked": True,
        "response_network_writes": 0, "participant_sessions_run": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
