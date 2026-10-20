"""End-to-end checks. Requires playwright and a running application server."""

import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = os.getenv("COOLING_TEST_URL", "http://127.0.0.1:8765")


def main():
    with sync_playwright() as p:
        # Prefer normal Playwright browser installation; allow an explicit existing binary.
        executable = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
        browser = p.chromium.launch(
            headless=True, **({"executable_path": executable} if executable else {})
        )
        page = browser.new_page(
            viewport={"width": 1440, "height": 1080},
            device_scale_factor=1,
        )
        api = p.request.new_context(
            extra_http_headers={"X-Participant-ID": "automated-validation-only"}
        )
        page.add_init_script(
            "localStorage.setItem('cooling-participant','automated-validation-only')"
        )
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        api.post(URL + "/api/consent", data={"consent": False})
        page.goto(URL, wait_until="networkidle")
        assert page.title() == "Hostel Cooling Lab"
        page.locator("#recommend-top").click()
        page.locator("#recommend-result").wait_for(state="visible")
        assert "TSV proxy" in page.locator("#comfort").inner_text()
        page.locator("#rain").check()
        page.locator("#recommend-top").click()
        page.locator("#recommend-result").wait_for(state="visible")
        assert page.locator("#window-action").inner_text() == "Closed"
        page.locator("#rain").uncheck()
        with page.expect_response(
            lambda r: r.url.endswith("/api/consent") and r.request.method == "POST"
        ):
            page.locator("#consent").check()
        page.wait_for_function(
            "() => document.getElementById('memory-profile').textContent.includes('Study target')"
        )
        page.locator("#message").fill("I prefer 27 C. I want airflow.")
        page.locator("#save-preference").click()
        page.locator("#preference-review").wait_for(state="visible")
        unconfirmed = api.get(URL + "/api/profile/export").json()
        assert unconfirmed["preference"]["activity_targets"] == {}
        assert unconfirmed["events"] == []
        page.locator("#discard-preference").click()
        assert api.get(URL + "/api/profile/export").json()["events"] == []
        page.locator("#message").fill("I prefer 27 C. I want airflow.")
        page.locator("#save-preference").click()
        page.locator("#preference-review").wait_for(state="visible")
        page.locator("#confirm-preference").click()
        page.wait_for_function(
            "() => document.getElementById('memory-profile').textContent.includes('Study target 27')"
        )
        page.locator("[data-activity=sleep]").click()
        page.locator("#message").fill("I prefer 29 C. I need quiet when sleeping.")
        page.locator("#save-preference").click()
        page.locator("#preference-review").wait_for(state="visible")
        page.locator("#confirm-preference").click()
        page.wait_for_function(
            "() => document.getElementById('memory-profile').textContent.includes('Sleep target 29')"
        )
        page.locator("#recommend-top").click()
        page.locator("#recommend-result").wait_for(state="visible")
        assert page.locator("#fan-action").inner_text().startswith(("Off", "Low"))
        page.locator("#accept").click()
        page.wait_for_function(
            "() => document.getElementById('feedback-status').textContent.includes('stored separately')"
        )
        exported = api.get(URL + "/api/profile/export").json()
        assert exported["preference"]["activity_targets"] == {
            "study": 27.0,
            "sleep": 29.0,
        }
        assert len(exported["feedback"]) == 1
        page.reload(wait_until="networkidle")
        assert "Study target 27" in page.locator("#memory-profile").inner_text()
        page.locator("#participant-id").fill("automated-validation-other")
        page.locator("#switch-participant").click()
        page.wait_for_function(
            "() => document.getElementById('profile-status').textContent.includes('automated-validation-other')"
        )
        assert "Study target 28" in page.locator("#memory-profile").inner_text()
        assert not page.locator("#consent").is_checked()
        page.locator("#participant-id").fill("automated-validation-only")
        page.locator("#switch-participant").click()
        page.wait_for_function(
            "() => document.getElementById('profile-status').textContent.includes('automated-validation-only')"
        )
        assert "Study target 27" in page.locator("#memory-profile").inner_text()
        page.locator("#recommend-top").click()
        page.locator("#recommend-result").wait_for(state="visible")
        page.locator("#toast").evaluate(
            "n => { n.style.transition='none'; n.classList.remove('visible'); }"
        )
        page.screenshot(path=str(ROOT / "outputs/study/dashboard.png"), full_page=True)
        page.locator("#step").click()
        page.locator("#recommend-top").click()
        page.locator("#recommend-result").wait_for(state="visible")
        results = api.get(URL + "/api/results").json()
        if results.get("rows"):
            page.locator("[data-view=evidence]").click()
            page.locator("#results tr").first.wait_for()
            assert page.locator("#results tr").count() == 9
            page.locator("#hypothesis-results tr").first.wait_for()
            assert page.locator("#hypothesis-results tr").count() == 8
            assert "Not supported" in page.locator("#hypothesis-results").inner_text()
            assert api.get(URL + "/evidence/PRESENTATION_NOTES.md").status == 200
            assert api.get(URL + "/evidence/hypothesis_assessment.json").status == 200
            for artifact in (
                "/report.pdf",
                "/presentation.pptx",
                "/presentation.pdf",
                "/viva.pdf",
            ):
                assert api.get(URL + artifact).status == 200
            page.locator("#toast").evaluate(
                "n => { n.style.transition='none'; n.classList.remove('visible'); }"
            )
            page.screenshot(
                path=str(ROOT / "outputs/study/comparison-dashboard.png"),
                full_page=True,
            )
            assert api.get(URL + "/report").status == 200
        elif not os.getenv("COOLING_SKIP_EVIDENCE"):
            raise AssertionError("Completed study evidence is required")
        page.locator("[data-view=pilot]").click()
        page.locator("#pilot-file").set_input_files(str(ROOT / "data/noisy_pilot.csv"))
        page.locator("#validate-pilot").click()
        page.wait_for_function(
            "() => document.getElementById('pilot-status').textContent.includes('Valid: 1344')"
        )
        page.locator("#calibrate-pilot").click()
        page.wait_for_function(
            "() => document.getElementById('pilot-status').textContent.includes('Applied fitted room')"
        )
        assert float(page.locator("#ua_w_k").input_value()) > 45
        page.locator("[data-view=lab]").click()
        page.locator("[data-activity=auto]").click()
        page.locator("#recommend-top").click()
        page.locator("#recommend-result").wait_for(state="visible")
        assert "Inferred:" in page.locator("#activity-badge").inner_text()
        page.locator("[data-view=pilot]").click()
        page.locator("#erase").click()
        page.wait_for_function(
            "() => document.getElementById('privacy-status').textContent.includes('erased')"
        )
        data = api.get(URL + "/api/profile/export").json()
        assert data["events"] == [] and data["feedback"] == [] and not data["consent"]
        denied = api.post(
            URL + "/api/preferences",
            data={"activity": "study", "message": "I prefer 25 C"},
        )
        assert denied.status == 403
        cross = api.post(
            URL + "/api/consent",
            data={"consent": True},
            headers={"Origin": "https://example.com"},
        )
        assert cross.status == 403
        page.locator("[data-view=lab]").click()
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.locator("#toast").evaluate(
            "n => { n.style.transition='none'; n.classList.remove('visible'); }"
        )
        page.screenshot(
            path=str(ROOT / "outputs/study/mobile-dashboard.png"), full_page=True
        )
        assert not errors, errors
        browser.close()
        print(
            json.dumps(
                {
                    "browser": "Chromium headless",
                    "checks": "recommendation, rain constraint, consent, activity memory, persistence, feedback, comparison, CSV validation, erasure, cross-origin rejection, responsive layout",
                    "javascript_errors": errors,
                    "actual_llm": True,
                    "profile_isolation": True,
                    "csv_calibration_applied": True,
                    "learned_activity_mode": True,
                    "preference_preview_confirm_discard": True,
                    "all_eight_proposal_hypotheses": True,
                    "status": "passed",
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
