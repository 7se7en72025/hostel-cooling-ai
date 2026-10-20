"""Presentation content sourced from the completed computations, without invented results."""

import json
from pathlib import Path


def write_presentation_content(output_dir):
    out = Path(output_dir)
    s = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    rows = {r["method"]: r for r in s["rows"]}
    ours, fixed = rows["ours"], rows["fixed"]
    language = s["language_evaluation"]
    cal = s["calibration"]
    routine = s["trained_models"]["routine"]
    sources = {
        "physics": "https://energyplus.readthedocs.io/en/stable/guides/engineering-reference/2.1-basis-for-the-zone-and-air-system-integration.html",
        "adaptive": "https://pythermalcomfort.readthedocs.io/en/latest/documentation/models.html",
        "model": "https://huggingface.co/Qwen/Qwen3-4B-GGUF",
        "llama": "https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md",
        "prior_work": "https://doi.org/10.1016/j.enbuild.2026.117181",
    }
    slides = [
        {
            "title": "Cooling for student hostels",
            "subtitle": "CE F417 + CE F423",
            "lines": [
                "Preference memory, building physics and constrained room control",
                "Completed simulated research project",
            ],
            "notes": "All room and occupant outcomes are simulated. The local transformer, training and exported computations actually ran. Course instructor: Prof. Rajiv Gupta.",
        },
        {
            "title": "Research question",
            "lines": [
                "Can retained student preferences guide fan, window and curtain decisions?",
                "F417: language, memory and AI comparisons",
                "F423: airflow, solar gains and energy",
                "Study, sleep and away can require different settings",
            ],
            "notes": "Source proposals define the combined scope. Conversation-based comfort learning already exists: "
            + sources["prior_work"],
        },
        {
            "title": "Implemented system",
            "lines": [
                "1. Consented feedback updates an activity-specific profile",
                "2. Heat and moisture balances estimate room conditions",
                "3. Fuzzy comfort and a GA score legal controls",
                "4. Suggestions, evidence and self-reports persist locally",
                "Learned activity inference and CSV calibration are available in the application",
            ],
            "notes": "Source: implemented modules preferences.py, physics.py, optimizer.py, server.py and routines.py. Self-reports remain separate from simulation labels.",
        },
        {
            "title": "Room model and calibration",
            "table": [
                ["Parameter", "Synthetic plant", "Fitted controller"],
                [
                    "UA / W K-1",
                    str(s["plant_room"]["ua_w_k"]),
                    str(s["room"]["ua_w_k"]),
                ],
                [
                    "C / MJ K-1",
                    str(s["plant_room"]["capacity_j_k"] / 1e6),
                    str(s["room"]["capacity_j_k"] / 1e6),
                ],
                ["Area / m2", "12", "12"],
            ],
            "lines": [
                "C dT/dt = G (Tout - T) + solar + internal gains + fan power",
                "Fan electrical heat and perceived airflow relief remain separate",
            ],
            "notes": "The fitted parameters use separate noisy observations and can be biased. Model structure context: "
            + sources["physics"],
        },
        {
            "title": "Actual local preference learning",
            "lines": [
                s["model_provenance"]["model"],
                "Pinned model revision and SHA256; local inference, no API key",
                "Structured values require exact-message evidence quotes",
                "Separate study and sleep targets survive activity changes",
                "Invalid values and unsupported evidence cannot silently change memory",
            ],
            "notes": "Model source: "
            + sources["model"]
            + ". Inference API: "
            + sources["llama"]
            + ". Actual prompts and outputs: llm_inference.jsonl.",
        },
        {
            "title": "Saved learning models",
            "lines": [
                f"Comfort ANN: {s['ann_validation']['mae_tsv']:.3f} TSV holdout MAE",
                "2,000 training and 400 independent synthetic holdout points",
                f"Routine model: {routine['accuracy']*100:.1f}% chronological test accuracy",
                f"Majority routine baseline: {routine['majority_baseline_accuracy']*100:.1f}%",
                "Saved weights, counts, datasets and validation metadata accompany the project",
            ],
            "notes": "All model validation labels are synthetic. Routine split: 14 train days and seven later test days. Source: models/ann_validation.json and routine_validation.json.",
        },
        {
            "title": "Matched experimental design",
            "lines": [
                f"{s['days_per_seed']} days per seed; seeds {s['seeds']}",
                "15-minute physics, hourly control decisions for every policy",
                f"{len(rows)} methods, separate closed-loop room trajectories",
                "Same forcing, initial state and explicit constraints",
                "Survey and no-physics ablations isolate memory and lookahead",
            ],
            "notes": "All actions apply, including proxy-declined suggestions. Comfort excludes away intervals. The generic LLM receives no personal history or numerical room forecast.",
        },
        {
            "title": "F417 comparison",
            "table": [["Controller", "Wh/day", "Mean |TSV|", "Violation %"]]
            + [
                [
                    m,
                    f"{rows[m]['fan_wh_day']:.1f}",
                    f"{rows[m]['mean_abs_tsv_proxy']:.2f}",
                    f"{rows[m]['comfort_violation_pct']:.1f}",
                ]
                for m in s["course_comparisons"]["CE_F417"]
            ],
            "lines": ["Synthetic comfort outcomes; actual generic LLM inference"],
            "notes": "Source: CE_F417_comparison.csv. Adaptive reference uses a documented fallback outside awake/study applicability. "
            + sources["adaptive"],
        },
        {
            "title": "F423 fan electricity",
            "chart": {
                "kind": "bar",
                "categories": s["course_comparisons"]["CE_F423"],
                "values": [
                    round(rows[m]["fan_wh_day"], 1)
                    for m in s["course_comparisons"]["CE_F423"]
                ],
                "unit": "Fan Wh/day",
            },
            "lines": [
                "Energy must be interpreted alongside occupied discomfort",
                f"Proposed period fan EPI: {ours['fan_epi_period_kwh_m2']:.4f} kWh/m2",
            ],
            "notes": "Source: CE_F423_comparison.csv. EPI covers only fan electricity during this trial, not annual whole-building EPI.",
        },
        {
            "title": "Comfort and energy trade-off",
            "lines": [
                f"Ours: {ours['fan_wh_day']:.1f} Wh/day; {ours['comfort_violation_pct']:.1f}% violations",
                f"Fixed: {fixed['fan_wh_day']:.1f} Wh/day; {fixed['comfort_violation_pct']:.1f}% violations",
                f"Fan energy change: {ours['fan_energy_change_vs_fixed_pct']:+.1f}%",
                f"Comfort violation change: {ours['comfort_violation_pct']-fixed['comfort_violation_pct']:+.2f} percentage points",
                "Synthetic results establish a scenario trade-off, not a human benefit",
            ],
            "notes": "Source: summary.json and paired_comparisons.csv. Paired weather-seed intervals are exploratory with n=3; no participant inference.",
        },
        {
            "title": "Memory and physics ablations",
            "table": [["Method", "Wh/day", "Violation %", "Accept proxy %"]]
            + [
                [
                    m,
                    f"{rows[m]['fan_wh_day']:.1f}",
                    f"{rows[m]['comfort_violation_pct']:.1f}",
                    f"{rows[m]['acceptance_proxy_pct']:.1f}",
                ]
                for m in ["ours", "survey", "no_physics", "physics"]
            ],
            "lines": [
                "The survey starts with the same initial profile",
                "A scripted target change reaches only memory-enabled policies",
            ],
            "notes": "Source: comparison.csv and conversation_evidence.json. The small scripted experiment tests retention mechanically; it is not an actual conversation-versus-survey trial.",
        },
        {
            "title": "Language evaluation",
            "lines": [
                f"24 fixed held-out synthetic phrases",
                f"Exact-match accuracy: {language['exact_match_accuracy']*100:.1f}%",
                f"Field precision / recall: {language['field_precision']:.3f} / {language['field_recall']:.3f}",
                f"Cross-activity persistence: {language['memory_context_persistent']}",
                "All failures and safe rejections remain in the evidence",
                "The app requires review and confirmation before saving preferences",
            ],
            "notes": "Source: language_evaluation.json. This is real local model inference, not parser output. Phrases include negation, unrelated observations, invalid values and mixed contexts.",
        },
        {
            "title": "Held-out room prediction",
            "chart": {
                "kind": "bar",
                "categories": ["Calibrated RC", "Persistence"],
                "values": [
                    round(cal["test_rmse_c"], 3),
                    round(cal["persistence_test_rmse_c"], 3),
                ],
                "unit": "Held-out RMSE / C",
            },
            "lines": [
                "14 days of noisy synthetic observations",
                "Chronological 80/20 transition split",
                "Low prediction error does not prove parameter identifiability",
            ],
            "notes": "Source: calibration.json and noisy_pilot_metadata.json. Parameter selection never uses test transitions.",
        },
        {
            "title": "Objective-weight sensitivity",
            "chart": {
                "kind": "line",
                "categories": [str(r["energy_weight"]) for r in s["sensitivity"]],
                "values": [round(r["fan_wh_day"], 1) for r in s["sensitivity"]],
                "unit": "Fan Wh/day",
            },
            "lines": [
                "All six predeclared energy weights are reported",
                "Same three seeds, three days per weight",
                "Comfort outcomes accompany the energy curve in sensitivity.csv",
            ],
            "notes": "This sweep illustrates objective dependence. It does not select a winning weight after observing the test outcomes.",
        },
        {
            "title": "Completed deliverables",
            "lines": [
                "Working local application with actual transformer requests",
                "Saved ANN and routine models, plus material and calibration tools",
                "Both course baseline sets, ablations and sensitivity analysis",
                "Raw interval data, inference journals and automated checks",
                "Reproducible setup, complete report and source repository",
            ],
            "notes": "The approved scope is a completed simulated course project. Physical sensors, metered human outcomes and a 20-50 room field study are separate empirical work.",
        },
        {
            "title": "Limits and interpretation",
            "lines": [
                "One-node room physics omits radiant and spatial effects",
                "Comfort labels and acceptance derive from assumed synthetic occupants",
                "LLM extraction can miss or misinterpret phrases",
                "No human effectiveness or building-certification claim",
                "A measured, consented field study would test external validity",
            ],
            "notes": "Preserve the distinction between completed software and unmeasured real-world benefit. The project reports unfavorable outcomes instead of manufacturing positive hypotheses.",
        },
    ]
    (out / "presentation_data.json").write_text(
        json.dumps(
            {
                "title": "Cooling for student hostels",
                "slides": slides,
                "sources": sources,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    lines = [
        "# Final presentation and viva notes",
        "",
        "Use the recorded study results below. The project contains actual local transformer inference and explicitly synthetic room/occupant outcomes.",
        "",
    ]
    for i, slide in enumerate(slides, 1):
        lines += [f"## {i}. {slide['title']}", ""]
        lines += ["- " + line for line in slide.get("lines", [])]
        if "table" in slide:
            table = slide["table"]
            lines += [
                "",
                "| " + " | ".join(table[0]) + " |",
                "| " + " | ".join("---" for _ in table[0]) + " |",
            ]
            lines += ["| " + " | ".join(row) + " |" for row in table[1:]]
        lines += ["", slide["notes"], ""]
    (out / "PRESENTATION_NOTES.md").write_text("\n".join(lines), encoding="utf-8")
    return slides
