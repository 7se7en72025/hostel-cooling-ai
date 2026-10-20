"""Held-out semantic extraction and actual model memory evaluation."""

import json
import statistics
import tempfile
import time
from pathlib import Path
from .domain import Preference
from .preferences import Memory

from .paths import ROOT


def flatten(patch):
    result = {}
    for key, value in patch.items():
        if key == "activity_targets":
            for activity, target in value.items():
                result[f"target_{activity}"] = target
        else:
            result[key] = value
    return result


def evaluate_language(backend, output_dir):
    dataset = ROOT / "data" / "preference_benchmark.json"
    if not dataset.exists():
        dataset = Path(__file__).parent / "resources" / "preference_benchmark.json"
    cases = json.loads(dataset.read_text(encoding="utf-8"))["cases"]
    records = []
    tp = fp = fn = 0
    exact = 0
    for case in cases:
        started = time.perf_counter()
        rejected = False
        error = None
        try:
            actual = backend.extract(case["message"], case["activity"], Preference())
        except (ValueError, RuntimeError) as exc:
            actual = {}
            rejected = True
            error = str(exc)
        expected_flat = flatten(case["expected"])
        actual_flat = flatten(actual)
        match = actual_flat == expected_flat and (
            not rejected or case.get("expected_rejection", False)
        )
        if case.get("expected_rejection") and actual_flat:
            match = False
        exact += match

        def equal_value(a, b):
            return isinstance(a, bool) == isinstance(b, bool) and a == b

        for key, value in actual_flat.items():
            if key in expected_flat and equal_value(value, expected_flat[key]):
                tp += 1
            else:
                fp += 1
        for key, value in expected_flat.items():
            if key not in actual_flat or not equal_value(actual_flat[key], value):
                fn += 1
        records.append(
            {
                **case,
                "actual": actual,
                "exact_match": match,
                "rejected": rejected,
                "error": error,
                "elapsed_ms": (time.perf_counter() - started) * 1000,
            }
        )
    with tempfile.TemporaryDirectory() as folder:
        memory = Memory(Path(folder) / "memory.sqlite3")
        memory.consent("synthetic", True)
        first = memory.update(
            "synthetic", "I prefer 27 C. I want airflow.", "study", backend
        )
        second = memory.update(
            "synthetic",
            "I prefer 29 C. Please keep the fan low when I sleep.",
            "sleep",
            backend,
        )
        reload = Memory(memory.path).profile("synthetic")
        persistent = reload["preference"]["activity_targets"] == {
            "study": 27,
            "sleep": 29,
        }
        memory.consent("synthetic", False)
        erased = (
            not memory.profile("synthetic")["consent"]
            and not memory.export("synthetic")["events"]
        )
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    result = {
        "backend": backend.name,
        "model_provenance": getattr(backend, "provenance", None),
        "provenance": "fixed held-out synthetic phrases; outputs from the pinned transformer",
        "n": len(cases),
        "exact_match_accuracy": exact / len(cases),
        "field_precision": precision,
        "field_recall": recall,
        "field_f1": (
            2 * precision * recall / (precision + recall) if precision + recall else 0
        ),
        "true_positive_fields": tp,
        "false_positive_fields": fp,
        "missed_or_wrong_fields": fn,
        "median_request_ms": statistics.median(r["elapsed_ms"] for r in records),
        "memory_context_persistent": persistent,
        "consent_erasure_passed": erased,
        "memory_updates": [first, second],
        "cases": records,
    }
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "language_evaluation.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result
