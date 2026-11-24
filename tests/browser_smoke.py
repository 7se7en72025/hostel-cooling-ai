"""End-to-end checks. Requires playwright and a running application server."""

import json
import os
from contextlib import ExitStack
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = os.getenv("COOLING_TEST_URL", "http://127.0.0.1:8765")
SCREENSHOTS = Path(os.getenv("COOLING_TEST_SCREENSHOTS", ROOT / "build/browser-smoke"))


def main():
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p, ExitStack() as cleanup:
        # Prefer normal Playwright browser installation; allow an explicit existing binary.
        executable = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
        browser = p.chromium.launch(
            headless=True, **({"executable_path": executable} if executable else {})
        )
        page = browser.new_page(
            viewport={"width": 1440, "height": 1080},
            device_scale_factor=1,
        )
        alias = f"smoke-{uuid4().hex[:16]}"
        other = f"{alias}-other"

        def test_profile(name):
            client = p.request.new_context(
                extra_http_headers={"X-Participant-ID": name}
            )
            cleanup.callback(client.dispose)
            cleanup.callback(client.post, URL + "/api/consent", data={"consent": False})
            return client

        api = test_profile(alias)
        test_profile(other)
        page.add_init_script(
            f"localStorage.setItem('cooling-participant', {json.dumps(alias)})"
        )
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        status = api.get(URL + "/api/status").json()
        if os.getenv("COOLING_TEST_REQUIRE_LLM") == "1":
            assert status["real_llm"], status["inference_mode"]
        page.goto(URL, wait_until="networkidle")
        assert page.title() == "Hostel Cooling Lab"
        indoor = page.locator("#indoor_c")
        original = indoor.input_value()
        before_example = api.get(URL + "/api/profile/export").json()
        indoor.fill("32.5")
        example_button = page.get_by_role("button", name="Try the rain example")
        example_button.click()
        example = page.locator("#rain-example-results")
        example.wait_for(state="visible")
        assert example.locator("strong").all_text_contents() == [
            "Window open",
            "Window closed",
        ]
        assert indoor.input_value() == "32.5"
        assert api.get(URL + "/api/profile/export").json() == before_example
        page.get_by_role("button", name="Close example").click()
        assert example_button.get_attribute("aria-expanded") == "false"
        assert example_button.evaluate("button => button === document.activeElement")
        indoor.fill(original)

        sunlight = page.locator("#solar_w_m2")
        original_sunlight = sunlight.input_value()
        sunlight.fill("")
        page.locator("#recommend-top").click()
        assert sunlight.evaluate("input => input.validity.valueMissing")
        assert page.locator("#recommend-result").is_hidden()
        sunlight.fill(original_sunlight)

        def edit_while_recommending(route):
            indoor.fill(str(float(original) + 0.5))
            route.continue_()

        page.route("**/api/recommend", edit_while_recommending, times=1)
        page.locator("#recommend-top").click()
        page.wait_for_function(
            "() => !document.getElementById('recommend-top').disabled"
        )
        assert page.locator("#recommend-result").is_hidden()
        indoor.fill(original)
        page.locator("#recommend-top").click()
        page.locator("#recommend-result").wait_for(state="visible")
        assert page.locator("#comfort").inner_text() in {
            "Cold",
            "Cool",
            "Slightly cool",
            "Neutral",
            "Slightly warm",
            "Warm",
            "Hot",
        }
        assert (
            "modeled comfort score"
            in page.locator("#recommend-technical").text_content()
        )
        assert page.locator("#fixed-forecast").is_visible()
        assert "Wh fan electricity" in page.locator("#fixed-electricity").inner_text()
        assert page.locator("#forecast-chart polyline").count() == 2
        page.get_by_text("See the readings", exact=True).click()
        readings = page.locator("#forecast-readings tr")
        assert readings.count() == 5
        assert (
            readings.first.locator("td").first.inner_text()
            == f"{float(original):.1f} °C"
        )
        assert (
            readings.last.locator("td").first.inner_text()
            == page.locator("#forecast-temperature").inner_text()
        )
        assert (
            readings.last.locator("td").nth(1).inner_text()
            == page.locator("#fixed-temperature").inner_text()
        )
        page.set_viewport_size({"width": 320, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.set_viewport_size({"width": 1440, "height": 1080})
        page.get_by_text("See the readings", exact=True).click()
        fixed_response = api.post(
            URL + "/api/recommend",
            data={"method": "fixed", "conditions": {"activity": "sleep", "rain": True}},
        )
        assert fixed_response.ok
        fixed_case = fixed_response.json()
        assert fixed_case["action"]["window"] == 0 and fixed_case["action"]["fan"] <= 1
        assert fixed_case["fixed_schedule"]["action"] == fixed_case["action"]
        assert fixed_case["fixed_schedule"]["trajectory"] == fixed_case["trajectory"]
        assert (
            fixed_case["fixed_schedule"]["one_hour_fan_wh"]
            == 4 * fixed_case["heat"]["fan_wh"]
        )
        hot_case = api.post(
            URL + "/api/recommend",
            data={
                "method": "expert",
                "conditions": {
                    "indoor_c": 49,
                    "outdoor_c": 47,
                    "hour": 20,
                    "solar_w_m2": 800,
                },
                "room": {"ua_w_k": 45, "capacity_j_k": 2_000_000},
            },
        )
        assert hot_case.ok and hot_case.json()["fixed_schedule"] is None
        overview = api.get(
            URL + page.get_by_role("link", name="Project PDF").get_attribute("href")
        )
        assert overview.ok and overview.headers["content-type"] == "application/pdf"
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
        page.get_by_text("Switch profile", exact=True).click()
        page.locator("#participant-id").fill(other)
        page.locator("#switch-participant").click()
        page.wait_for_function(
            f"() => document.getElementById('profile-status').textContent.startsWith('Profile: {other} /')"
        )
        assert "Study target 28" in page.locator("#memory-profile").inner_text()
        assert not page.locator("#consent").is_checked()
        page.locator("#participant-id").fill(alias)
        page.locator("#switch-participant").click()
        page.wait_for_function(
            f"() => document.getElementById('profile-status').textContent.startsWith('Profile: {alias} /')"
        )
        assert "Study target 27" in page.locator("#memory-profile").inner_text()
        page.locator("#recommend-top").click()
        page.locator("#recommend-result").wait_for(state="visible")
        page.locator("#toast").evaluate(
            "n => { n.style.transition='none'; n.classList.remove('visible'); }"
        )
        page.screenshot(path=str(SCREENSHOTS / "dashboard.png"), full_page=True)
        hour = page.locator("#hour")
        hour.fill("23.74999")
        page.locator("#recommend-top").click()
        page.locator("#recommend-result").wait_for(state="visible")
        page.locator("#step").click()
        assert hour.input_value() == "0"
        page.locator("#recommend-top").click()
        page.locator("#recommend-result").wait_for(state="visible")
        results = api.get(URL + "/api/results").json()
        if results.get("rows"):
            page.locator("[data-view=evidence]").click()
            if not status["study_available"]:
                page.wait_for_function(
                    "() => document.getElementById('experiment-status').textContent.includes('pinned local model')"
                )
                assert page.locator("#run-experiment").is_disabled()
                assert api.post(URL + "/api/experiment", data={"days": 7}).status == 403
            page.locator("#results tr").first.wait_for()
            assert page.locator("#results tr").count() == 9
            assert page.locator("#study-energy").inner_text() == "35% less"
            assert page.locator("#study-comfort").inner_text() == "2.4 points higher"
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
                path=str(SCREENSHOTS / "comparison-dashboard.png"),
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
        page.screenshot(path=str(SCREENSHOTS / "mobile-dashboard.png"), full_page=True)
        assert not errors, errors
        browser.close()
        print(
            json.dumps(
                {
                    "browser": "Chromium headless",
                    "checks": "rain example, numeric validation, forecast readings, recommendations, consent, activity memory, persistence, feedback, comparison, CSV validation, erasure, responsive layout",
                    "javascript_errors": errors,
                    "inference_mode": status["inference_mode"],
                    "actual_llm": status["real_llm"],
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
