"""Exercise the installed archive over HTTP and confirm its evidence scope in browsers."""
import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

from research.ml_repro_02.check_replay import API, main as verify_archive

STATUS = "BLOCKED_EXTERNAL_VALIDATION"


def main(api, web, offline, output):
    with urlopen(api + "/api/health", timeout=15) as response:
        assert response.status == 200
    with urlopen(api + API, timeout=15) as response:
        meta = json.load(response)
    assert meta["evidence_boundary"] == {"cohort": "PREVIOUSLY_INSPECTED_SIMULATION",
                                        "external_validation": STATUS, "alarm_meaning": "MODEL_RESIDUAL_ONLY"}
    for query in ("dataset_id=foreign", "method=SYSTEM_MAX_8", "threshold=2", "case=healthy"):
        try:
            urlopen(api + API + "/day?case=sa-plus-2&day=2018-10-20&" + query, timeout=15)
        except HTTPError as error:
            assert error.code == 422 and json.load(error)["detail"] == "ARCHIVE_CASE_AND_DAY_ONLY"
        else:
            raise AssertionError("Unexpected archive response for " + query)
    print("PASS live API evidence boundary and rejection of ambiguous or external requests", flush=True)
    verify_archive(api, web, offline, output)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width in (1440, 390):
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.goto(web + "/research/virtual-sensors")
            expect(page.get_by_role("region", name="Границы проверки")).to_be_visible(timeout=15000)
            expect(page.get_by_test_id("external-validation")).to_have_text(STATUS)
            page.close()
        browser.close()
    print("PASS explicit external validation status in desktop and mobile research UI")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", required=True)
    parser.add_argument("--web", required=True)
    parser.add_argument("--offline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(**vars(parser.parse_args()))
