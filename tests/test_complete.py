import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from hostel_cooling.ann import ComfortANN
from hostel_cooling.domain import Action, Conditions, Preference, Room
from hostel_cooling.llm import LocalLLM
from hostel_cooling.pilot import generate_noisy_pilot, calibrate
from hostel_cooling.preferences import Memory
from hostel_cooling.routines import RoutineModel, train_synthetic_routines


class CompleteProjectTests(unittest.TestCase):
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
