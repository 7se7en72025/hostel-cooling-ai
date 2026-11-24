"""Fail if the submission omits an actual model, a baseline, or raw evidence."""

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys
import re
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def verify(output_dir=None):
    from hostel_cooling.local_model import MODEL_SHA256
    from hostel_cooling.experiment import weather

    out = Path(output_dir or ROOT / "outputs/study")
    required = [
        "summary.json",
        "comparison.csv",
        "runs.csv",
        "trajectories.csv",
        "llm_inference.jsonl",
        "conversation_evidence.json",
        "language_evaluation.json",
        "calibration.json",
        "paired_comparisons.csv",
        "sensitivity.csv",
        "report.html",
        "Hostel_Cooling_Project_Report.pdf",
        "comparison.png",
        "trajectories.png",
        "hypothesis_assessment.json",
        "preference_change_phases.csv",
        "PRESENTATION_NOTES.md",
        "Hostel_Cooling_Final_Presentation.pptx",
        "Hostel_Cooling_Final_Presentation.pdf",
        "Hostel_Cooling_Viva_Guide.pdf",
    ]
    for name in required:
        assert (out / name).is_file() and (
            out / name
        ).stat().st_size > 0, f"Missing evidence: {name}"
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    expected = {
        "fixed",
        "expert",
        "adaptive",
        "ann",
        "physics",
        "generic_llm",
        "ours",
        "survey",
        "no_physics",
    }
    assert {r["method"] for r in summary["rows"]} == expected
    assert summary["complete"] and not summary["skipped"]
    assert (
        summary["real_llm_used"]
        and summary["model_provenance"]["sha256"] == MODEL_SHA256
    )
    assert summary["control_interval_minutes"] == 60
    assert len(summary["runs"]) == len(expected) * len(summary["seeds"])
    counts = Counter()
    energy = defaultdict(float)
    forcing = {
        seed: weather(summary["days_per_seed"], seed) for seed in summary["seeds"]
    }
    with (out / "trajectories.csv").open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            key = (int(row["seed"]), row["method"])
            counts[key] += 1
            energy[key] += float(row["fan_wh"])
            if row["activity"] == "away":
                assert int(row["fan"]) == 0
            if forcing[key[0]][int(row["step"])].rain:
                assert float(row["window"]) == 0
    for run in summary["runs"]:
        key = (run["seed"], run["method"])
        assert counts[key] == summary["days_per_seed"] * 96
        assert abs(energy[key] / summary["days_per_seed"] - run["fan_wh_day"]) < 1e-8
    inferences = [
        json.loads(line)
        for line in (out / "llm_inference.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    generated = {item["key"] for item in inferences if not item["cached"]}
    assert len(generated) >= 100, "Insufficient actual model inference evidence"
    assert all(item["model"]["sha256"] == MODEL_SHA256 for item in inferences)
    language = json.loads(
        (out / "language_evaluation.json").read_text(encoding="utf-8")
    )
    assert language["n"] == 24 and len(language["cases"]) == 24
    assert language["memory_context_persistent"] and language["consent_erasure_passed"]
    findings = json.loads(
        (out / "hypothesis_assessment.json").read_text(encoding="utf-8")
    )
    assert len(findings["hypotheses"]) == 8
    assert findings["pre_change_trajectories_identical"]
    with zipfile.ZipFile(out / "Hostel_Cooling_Final_Presentation.pptx") as deck:
        parts = deck.namelist()
        slides = [n for n in parts if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
        charts = [n for n in parts if re.fullmatch(r"ppt/charts/chart\d+\.xml", n)]
        notes = [
            n for n in parts if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n)
        ]
        workbooks = [
            n for n in parts if n.startswith("ppt/embeddings/") and n.endswith(".xlsx")
        ]
        table_count = sum(
            len(
                ET.fromstring(deck.read(n)).findall(
                    ".//{http://schemas.openxmlformats.org/drawingml/2006/main}tbl"
                )
            )
            for n in slides
        )
        assert len(slides) == 18 and len(charts) == 3 and table_count == 5
        assert len(notes) == 18 and len(workbooks) == 3
        assert deck.testzip() is None
    for file in [
        "comfort_ann.npz",
        "routine_model.json",
        "ann_validation.json",
        "routine_validation.json",
    ]:
        assert (ROOT / "models" / file).is_file()
    result = {
        "status": "passed",
        "required_methods": sorted(expected),
        "weather_seeds": summary["seeds"],
        "closed_loop_intervals": sum(counts.values()),
        "unique_actual_model_requests": len(generated),
        "language_cases": language["n"],
        "energy_accounting": "verified from raw trajectories",
        "away_and_rain_constraints": "verified across every simulated interval",
        "model_sha256": MODEL_SHA256,
        "trajectory_sha256": hashlib.sha256(
            (out / "trajectories.csv").read_bytes()
        ).hexdigest(),
        "final_presentation": {
            "editable_slides": len(slides),
            "native_charts": len(charts),
            "native_tables": table_count,
            "speaker_notes": len(notes),
        },
        "hypotheses_assessed": len(findings["hypotheses"]),
    }
    (out / "submission_verification.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8", newline="\n"
    )
    return result


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
