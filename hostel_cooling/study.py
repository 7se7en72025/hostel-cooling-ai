"""The complete simulated course study, including actual local-model inference."""

import csv
import json
from dataclasses import replace
from pathlib import Path
import numpy as np
import platform
import importlib.metadata
import subprocess
from .ann import ComfortANN
from .domain import Room
from .experiment import run_experiment
from .llm import get_backend
from .pilot import generate_noisy_pilot, calibrate
from .routines import train_synthetic_routines

from .paths import ROOT


def train_models(output_dir=None):
    out = Path(output_dir or ROOT / "models")
    out.mkdir(parents=True, exist_ok=True)
    ann = ComfortANN()
    ann.save(out / "comfort_ann.npz")
    (out / "ann_validation.json").write_text(
        json.dumps(ann.validation, indent=2), encoding="utf-8"
    )
    (out / "ann_loss.json").write_text(
        json.dumps(ann.loss_history, indent=2), encoding="utf-8"
    )
    with (out / "ann_dataset.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            ["temperature_c", "rh_pct", "air_speed_ms", "tsv_synthetic", "split"]
        )
        for i, (temp, rh, speed, vote) in enumerate(ann.training_data):
            writer.writerow(
                [
                    28 + temp * 6,
                    55 + rh * 30,
                    speed * 1.5,
                    vote,
                    "train" if i < 2000 else "test",
                ]
            )
    routine = train_synthetic_routines(out)
    return {"ann": ann.validation, "routine": routine}


def progress(item):
    print(json.dumps(item), flush=True)


def run_study(
    output_dir="outputs/study", days=7, seeds=(11, 23, 47), backend_kind="local"
):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    progress({"stage": "training"})
    trained = train_models()
    metadata = generate_noisy_pilot(ROOT / "data" / "noisy_pilot.csv")
    (ROOT / "data" / "noisy_pilot_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    progress({"stage": "calibration"})
    calibration = calibrate(ROOT / "data" / "noisy_pilot.csv", out / "calibration.json")
    estimated_room = Room(**calibration["selected_room"])
    plant_room = Room(**metadata["plant_room"])
    kwargs = {}
    if backend_kind == "local":
        kwargs = {
            "trace_path": out / "llm_inference.jsonl",
            "cache_path": ROOT / "runtime" / "study_model_cache.jsonl",
        }
    backend = get_backend(backend_kind, **kwargs)
    progress({"stage": "comparison", "model": backend.name})
    summary = run_experiment(
        out,
        days,
        seeds,
        backend,
        control_every=4,
        room=estimated_room,
        plant_room=plant_room,
        progress=progress,
        ann=ComfortANN.load(ROOT / "models" / "comfort_ann.npz"),
    )
    summary["calibration"] = calibration
    summary["trained_models"] = trained
    summary["study_version"] = "2.0.0"
    summary["complete"] = not summary["skipped"] and (
        summary["real_llm_used"]
        or summary.get("inference_mode") == "recorded-response replay"
    )
    summary["limitations"][
        0
    ] = "One-node RC model calibrated on noisy synthetic observations; real building validation remains outside the simulated scope."
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return finalize_study(out, backend)


def finalize_study(output_dir, backend=None):
    from .language_evaluation import evaluate_language
    from .analysis import analyze_study, sensitivity
    from .report import write_report

    out = Path(output_dir)
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    environment = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "matplotlib", "reportlab")
        },
    }
    try:
        gpu = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        environment["gpu"] = gpu.stdout.strip() or "not reported"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        environment["gpu"] = "not reported"
    (out / "environment.json").write_text(
        json.dumps(environment, indent=2), encoding="utf-8"
    )
    backend = backend or get_backend(
        "local",
        trace_path=out / "llm_inference.jsonl",
        cache_path=ROOT / "runtime" / "study_model_cache.jsonl",
    )
    progress({"stage": "held-out language evaluation"})
    language = evaluate_language(backend, out)
    summary["language_evaluation"] = {
        k: v for k, v in language.items() if k not in ("cases", "memory_updates")
    }
    progress({"stage": "objective sensitivity"})
    sweep = sensitivity(
        out,
        backend,
        Room(**summary["room"]),
        Room(**summary["plant_room"]),
        ComfortANN.load(ROOT / "models" / "comfort_ann.npz"),
    )
    summary["sensitivity"] = sweep
    summary["course_comparisons"] = {
        "CE_F417": ["expert", "adaptive", "ann", "generic_llm", "ours"],
        "CE_F423": ["fixed", "adaptive", "physics", "generic_llm", "ours"],
    }
    summary.setdefault("inference_mode", "actual model")
    for course, methods in summary["course_comparisons"].items():
        selected = [row for row in summary["rows"] if row["method"] in methods]
        with (out / (course + "_comparison.csv")).open(
            "w", newline="", encoding="utf-8"
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=selected[0], lineterminator="\n")
            writer.writeheader()
            writer.writerows(selected)
    summary["complete"] = (
        not summary["skipped"]
        and (
            summary["real_llm_used"]
            or summary.get("inference_mode") == "recorded-response replay"
        )
        and language["memory_context_persistent"]
        and language["consent_erasure_passed"]
    )
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    analyze_study(out)
    from .analysis import model_figures

    model_figures(ROOT / "models", out)
    write_report(summary, out)
    from .pdf_report import build_report

    build_report(out)
    from .presentation_content import write_presentation_content

    write_presentation_content(out)
    progress({"stage": "complete", "complete": summary["complete"]})
    return summary
