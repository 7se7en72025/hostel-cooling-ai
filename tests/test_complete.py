import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from hostel_cooling.ann import ComfortANN
from hostel_cooling.domain import Action, Conditions, Preference, Room
from hostel_cooling.llm import LocalLLM
from hostel_cooling.pilot import generate_noisy_pilot, calibrate
from hostel_cooling.preferences import Memory
from hostel_cooling.routines import RoutineModel, train_synthetic_routines


class CompleteProjectTests(unittest.TestCase):
    def test_inflight_preference_review_expires_after_consent_erasure(self):
        from concurrent.futures import ThreadPoolExecutor
        from http.server import ThreadingHTTPServer
        from queue import Queue
        from threading import Event, Thread
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        from hostel_cooling.llm import Offline
        from hostel_cooling.server import serve

        ready = Queue()
        extracting, release = Event(), Event()

        class TestServer(ThreadingHTTPServer):
            def server_activate(self):
                super().server_activate()
                ready.put(self)

        class SlowParser(Offline):
            def extract(self, text, activity, preference):
                extracting.set()
                if not release.wait(8):
                    raise RuntimeError("Test did not release the preference preview")
                return super().extract(text, activity, preference)

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with (
                patch("hostel_cooling.server.ROOT", root),
                patch("hostel_cooling.server.STUDY", root / "study"),
                patch("hostel_cooling.server.STUDY_RUNS", root / "runs"),
                patch("hostel_cooling.server.ThreadingHTTPServer", TestServer),
            ):
                worker = Thread(target=serve, args=(0, SlowParser()), daemon=True)
                worker.start()
                server = ready.get(timeout=8)

                def request(path, data=None):
                    body = json.dumps(data).encode() if data is not None else None
                    req = Request(
                        f"http://127.0.0.1:{server.server_port}{path}",
                        data=body,
                        headers={"Content-Type": "application/json"},
                    )
                    with urlopen(req, timeout=10) as response:
                        return json.load(response)

                try:
                    request("/api/consent", {"consent": True})
                    path = "/api/preferences/preview"
                    message = {"message": "I prefer 27 C", "activity": "study"}
                    with ThreadPoolExecutor(max_workers=1) as client:
                        pending = client.submit(request, path, message)
                        try:
                            self.assertTrue(extracting.wait(5))
                            request("/api/consent", {"consent": False})
                            request("/api/consent", {"consent": True})
                        finally:
                            release.set()
                        with self.assertRaises(HTTPError) as stale:
                            pending.result(timeout=8)
                        self.assertEqual(stale.exception.code, 409)
                        stale.exception.close()
                    self.assertEqual(request("/api/profile/export")["events"], [])
                    fresh = request(path, message)
                    confirmed = request(
                        "/api/preferences/confirm",
                        {"proposal_id": fresh["proposal_id"], "accept": True},
                    )
                    self.assertEqual(
                        confirmed["preference"]["activity_targets"]["study"], 27
                    )
                finally:
                    server.shutdown()
                    worker.join(timeout=8)

    def test_dashboard_recovers_latest_finished_study(self):
        from hostel_cooling.server import FINAL_RUN_FILES, latest_study_job

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for index, state in enumerate(
                ("complete", "complete", "partial", "invalid"), start=1
            ):
                run_dir = root / f"{index:016x}"
                run_dir.mkdir()
                for name in FINAL_RUN_FILES if state != "partial" else ("report.html",):
                    (run_dir / name).touch()
                os.utime(run_dir / "report.html", (index, index))
                summary = {"days_per_seed": 7, "complete": True, "rows": [1, 2, 3]}
                (run_dir / "summary.json").write_text(
                    json.dumps(summary) if state != "invalid" else "{", encoding="utf-8"
                )
            with patch("hostel_cooling.server.STUDY_RUNS", root):
                result = latest_study_job()
            self.assertEqual(result["state"], "complete")
            self.assertEqual(result["methods"], 3)
            self.assertEqual(
                result["report_url"], "/study-runs/0000000000000002/report.html"
            )

    def test_study_rejects_submitted_or_existing_outputs_before_inference(self):
        from hostel_cooling.study import run_study

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            submitted = root / "outputs/study"
            submitted.mkdir(parents=True)
            previous = root / "build/previous"
            previous.mkdir(parents=True)
            evidence = previous / "summary.json"
            evidence.write_text("previous result", encoding="utf-8")
            with (
                patch("hostel_cooling.study.ROOT", root),
                patch("hostel_cooling.study.get_backend") as get_backend,
            ):
                with self.assertRaisesRegex(ValueError, "separate output directory"):
                    run_study(submitted / "replay", backend_kind="replay")
                with self.assertRaisesRegex(ValueError, "empty directory"):
                    run_study(previous)
                get_backend.assert_not_called()
            self.assertFalse((submitted / "replay").exists())
            self.assertEqual(evidence.read_text(encoding="utf-8"), "previous result")

    def test_proposal_findings_match_frozen_trial_and_preserve_negative_result(self):
        import shutil
        from hostel_cooling.conclusions import assess_hypotheses

        source = Path(__file__).resolve().parents[1] / "outputs/study"
        with tempfile.TemporaryDirectory() as folder:
            for name in (
                "summary.json",
                "conversation_evidence.json",
                "trajectories.csv",
            ):
                shutil.copy2(source / name, Path(folder) / name)
            result = assess_hypotheses(folder)
            self.assertTrue(result["pre_change_trajectories_identical"])
            hypotheses = {h["id"]: h for h in result["hypotheses"]}
            self.assertEqual(len(hypotheses), 8)
            self.assertEqual(
                hypotheses["F417 H4"]["verdict"], "Not supported in this configuration"
            )
            self.assertAlmostEqual(
                result["post_change_acceptance_difference_pp"], 9.696969696969695
            )
            self.assertTrue(
                all(
                    r["conversation_absolute_error_c"] == 0
                    for r in result["target_recovery"]
                )
            )

    def test_reviewed_memory_requires_current_consent_and_context(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = Memory(Path(folder) / "state.db")
            memory.consent("one", True)
            before = memory.profile("one")["preference"]
            patch = {"activity_targets": {"study": 27.0}}
            result = memory.confirm_patch(
                "one", "I prefer 27 C", "study", patch, "test model", before
            )
            self.assertEqual(result["preference"]["activity_targets"]["study"], 27)
            self.assertIn(
                "user confirmed", memory.profile("one")["events"][0]["backend"]
            )
            with self.assertRaises(ValueError):
                memory.confirm_patch("one", "old", "study", patch, "test model", before)
            memory.consent("one", False)
            with self.assertRaises(PermissionError):
                memory.confirm_patch("one", "old", "study", patch, "test model", before)
            self.assertEqual(memory.profile("one")["events"], [])

    def test_material_resistance_and_added_insulation(self):
        from hostel_cooling.envelope import estimate_envelope

        base = estimate_envelope()
        insulation = {
            "name": "Illustrative user insulation",
            "thickness_m": 0.05,
            "conductivity_w_mk": 0.04,
            "density_kg_m3": 30,
            "specific_heat_j_kgk": 1400,
        }
        changed = estimate_envelope(layers=base["layers"] + [insulation])
        self.assertLess(changed["room"]["ua_w_k"], base["room"]["ua_w_k"])
        self.assertGreater(
            changed["room"]["capacity_j_k"], base["room"]["capacity_j_k"]
        )
        self.assertAlmostEqual(base["wall_u_w_m2k"], 1 / (0.13 + 0.04 + 0.2 / 1.729577))

    def test_saved_neural_model_preserves_predictions(self):
        model = ComfortANN()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ann.npz"
            model.save(path)
            loaded = ComfortANN.load(path)
            for temp in (24, 28, 33):
                c = Conditions(indoor_c=temp)
                for fan in range(4):
                    self.assertEqual(
                        model.predict(c, Room(), Action(fan)),
                        loaded.predict(c, Room(), Action(fan)),
                    )
            self.assertEqual(model.validation, loaded.validation)

    def test_routine_generalizes_to_chronological_holdout(self):
        with tempfile.TemporaryDirectory() as folder:
            result = train_synthetic_routines(folder)
            self.assertGreater(result["accuracy"], 0.85)
            self.assertGreater(result["accuracy"], result["majority_baseline_accuracy"])
            model = RoutineModel.load(Path(folder) / "routine_model.json")
            self.assertEqual(model.predict(3)["activity"], "sleep")
            self.assertEqual(model.predict(14)["activity"], "away")
            self.assertAlmostEqual(sum(model.predict(14)["probabilities"].values()), 1)

    def test_personal_observations_are_consent_gated_and_erased(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = Memory(Path(folder) / "state.db")
            memory.observe_activity("one", 16, 0, "study")
            self.assertEqual(memory.export("one")["activity_observations"], [])
            memory.consent("one", True)
            for _ in range(10):
                memory.observe_activity("one", 16, 0, "study")
            self.assertEqual(memory.routine("one", 16)["activity"], "study")
            memory.save_room_model("one", {"selected_room": {"ua_w_k": 58}})
            self.assertIsNone(memory.room_model("two"))
            self.assertEqual(memory.export("two")["activity_observations"], [])
            memory.consent("one", False)
            self.assertEqual(memory.export("one")["activity_observations"], [])
            self.assertIsNone(memory.room_model("one"))

    def test_grounded_extraction_repairs_evidence_without_rule_fallback(self):
        model = LocalLLM.__new__(LocalLLM)
        answers = iter(
            [
                {
                    "temperature_c": None,
                    "temperature_activity": None,
                    "temperature_quote": "",
                    "sleep_fan_limit": 1,
                    "sleep_fan_quote": "a phrase absent from this message",
                    "study_airflow": None,
                    "airflow_quote": "",
                },
                {"supported": True, "quote": "quiet during sleep"},
            ]
        )
        model.chat = lambda *args: next(answers)
        actual = model.extract("I need quiet during sleep", "sleep", Preference())
        self.assertEqual(actual, {"sleep_max_fan": 1, "noise_weight": 1.2})

    def test_unverified_quotes_cannot_change_preferences(self):
        model = LocalLLM.__new__(LocalLLM)
        answers = iter(
            [
                {
                    "temperature_c": 24,
                    "temperature_activity": "study",
                    "temperature_quote": "made up quote",
                    "sleep_fan_limit": None,
                    "sleep_fan_quote": "",
                    "study_airflow": None,
                    "airflow_quote": "",
                },
                {"supported": False, "quote": ""},
            ]
        )
        model.chat = lambda *args: next(answers)
        self.assertEqual(model.extract("Thank you", "study", Preference()), {})

    def test_noisy_room_fit_uses_real_holdout_and_nonzero_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "observations.csv"
            metadata = generate_noisy_pilot(path, days=3)
            result = calibrate(path, Path(folder) / "fit.json")
            self.assertGreater(result["test_rmse_c"], 0.05)
            self.assertLess(result["test_rmse_c"], 0.35)
            self.assertEqual(
                result["train_transitions"] + result["test_transitions"],
                metadata["rows"] - 1,
            )


if __name__ == "__main__":
    unittest.main()
