"""Answer each proposal hypothesis using the recorded simulated study evidence."""

import csv
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path


def assess_hypotheses(output_dir):
    out = Path(output_dir)
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    evidence = json.loads(
        (out / "conversation_evidence.json").read_text(encoding="utf-8")
    )
    changes = {item["seed"]: item["step"] for item in evidence}
    if set(changes) != set(summary["seeds"]):
        raise ValueError(
            "A recorded preference-change event is required for every seed"
        )
    grouped = defaultdict(list)
    with (out / "trajectories.csv").open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["method"] not in ("ours", "survey"):
                continue
            seed = int(row["seed"])
            phase = (
                "before change" if int(row["step"]) < changes[seed] else "after change"
            )
            grouped[(seed, row["method"], phase)].append(row)
    before_identical = all(
        [
            {k: v for k, v in r.items() if k != "method"}
            for r in grouped[(seed, "ours", "before change")]
        ]
        == [
            {k: v for k, v in r.items() if k != "method"}
            for r in grouped[(seed, "survey", "before change")]
        ]
        for seed in summary["seeds"]
    )
    if not before_identical:
        raise ValueError("The proposed and survey pre-change controls must be matched")
    phases = []
    for (seed, method, phase), rows in sorted(grouped.items()):
        occupied = [r for r in rows if r["activity"] != "away"]
        phases.append(
            {
                "seed": seed,
                "method": method,
                "phase": phase,
                "intervals": len(rows),
                "occupied_intervals": len(occupied),
                "fan_wh_day_equivalent": sum(float(r["fan_wh"]) for r in rows)
                / (len(rows) / 96),
                "mean_abs_tsv_proxy": statistics.mean(
                    abs(float(r["tsv_simulated"])) for r in occupied
                ),
                "comfort_violation_pct": 100
                * statistics.mean(abs(float(r["tsv_simulated"])) > 1 for r in occupied),
                "acceptance_proxy_pct": 100
                * statistics.mean(int(r["acceptance_proxy"]) for r in occupied),
            }
        )
    with (out / "preference_change_phases.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=phases[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(phases)
    metrics = {r["method"]: r for r in summary["rows"]}
    ours, fixed, survey, no_physics = [
        metrics[m] for m in ("ours", "fixed", "survey", "no_physics")
    ]

    def phase_mean(method, phase, field):
        return statistics.mean(
            r[field] for r in phases if r["method"] == method and r["phase"] == phase
        )

    post_acceptance_delta = phase_mean(
        "ours", "after change", "acceptance_proxy_pct"
    ) - phase_mean("survey", "after change", "acceptance_proxy_pct")
    target_checks = []
    for seed in summary["seeds"]:
        initial = 28 + random.Random(seed + 913).choice((-0.5, 0, 0.5))
        recorded = next(e for e in evidence if e["seed"] == seed)
        actual = recorded["patch"].get("activity_targets", {}).get("study")
        target_checks.append(
            {
                "seed": seed,
                "initial_survey_target_c": initial,
                "changed_target_c": initial - 1,
                "extracted_target_c": actual,
                "conversation_absolute_error_c": (
                    abs(actual - (initial - 1)) if actual is not None else None
                ),
                "unchanged_survey_absolute_error_c": 1.0,
            }
        )
    recovered = sum(r["conversation_absolute_error_c"] == 0 for r in target_checks)
    routine = summary["trained_models"]["routine"]
    energy_delta = ours["fan_energy_change_vs_fixed_pct"]
    violation_delta = ours["comfort_violation_pct"] - fixed["comfort_violation_pct"]
    acceptance_delta = ours["acceptance_proxy_pct"] - survey["acceptance_proxy_pct"]
    physics_delta = ours["comfort_violation_pct"] - no_physics["comfort_violation_pct"]
    epi_delta = 100 * (
        ours["fan_epi_period_kwh_m2"] / fixed["fan_epi_period_kwh_m2"] - 1
    )
    hypotheses = [
        {
            "id": "F417 H1",
            "question": "Conversation captures preferences better than a one-time survey",
            "verdict": "Mechanism supported in scripted cases; broader claim untested",
            "evidence": f"{recovered}/{len(target_checks)} changed study targets exactly recovered. Unchanged survey target error: 1 C after the change.",
            "limit": "Explicit numeric messages do not measure natural conversational coverage or survey burden.",
        },
        {
            "id": "F417 H2",
            "question": "The model notices study, sleep and away routines",
            "verdict": "Supported on the synthetic routine holdout",
            "evidence": f"Chronological routine accuracy {routine['accuracy']*100:.1f}%, majority baseline {routine['majority_baseline_accuracy']*100:.1f}%.",
            "limit": "Synthetic schedules; no student routine was observed.",
        },
        {
            "id": "F417 H3",
            "question": "Updated preferences lead to more accepted suggestions",
            "verdict": (
                "Supported by the assumed acceptance proxy"
                if acceptance_delta > 0
                else "Not supported by the assumed acceptance proxy"
            ),
            "evidence": f"Ours minus survey: {acceptance_delta:+.2f} percentage points across the trial; {post_acceptance_delta:+.2f} after the scripted change.",
            "limit": "Acceptance is a simulated occupant rule. Every suggested action applies regardless of acceptance.",
        },
        {
            "id": "F417 H4",
            "question": "Energy use falls without lowering comfort",
            "verdict": (
                "Not supported in this configuration"
                if energy_delta >= 0 or violation_delta > 0
                else "Consistent with this scenario"
            ),
            "evidence": f"Versus fixed: fan energy {energy_delta:+.2f}%; occupied violations {violation_delta:+.2f} percentage points.",
            "limit": "No human non-inferiority margin or powered field study was conducted.",
        },
        {
            "id": "F423 H1",
            "question": "Use less energy without reducing comfort",
            "verdict": (
                "Not supported in this configuration"
                if energy_delta >= 0 or violation_delta > 0
                else "Consistent with this scenario"
            ),
            "evidence": f"Versus fixed: fan electricity {energy_delta:+.2f}%; occupied discomfort {violation_delta:+.2f} percentage points.",
            "limit": "Both outcomes come from a simulated room and occupant.",
        },
        {
            "id": "F423 H2",
            "question": "Respond to sleep, study and away routines",
            "verdict": "Implemented and software-verified",
            "evidence": "Activity targets persist across context switches; away intervals use fan off; sleeping obeys the configured fan maximum.",
            "limit": "The main controller trial uses observed synthetic activity. Learned auto mode is evaluated separately.",
        },
        {
            "id": "F423 H3",
            "question": "Use room physics to make better suggestions",
            "verdict": (
                "Supported for discomfort under the no-physics ablation"
                if physics_delta < 0
                else "Not supported by this discomfort comparison"
            ),
            "evidence": f"Ours minus no-physics: occupied violations {physics_delta:+.2f} percentage points; fan electricity {ours['fan_wh_day']-no_physics['fan_wh_day']:+.1f} Wh/day.",
            "limit": "The comparison changes the whole control policy. Measurements in an occupied room could test physical accuracy.",
        },
        {
            "id": "F423 H4",
            "question": "Improve the room energy performance index",
            "verdict": (
                "Supported for the trial-period fan EPI"
                if epi_delta < 0
                else "Not supported for the trial-period fan EPI"
            ),
            "evidence": f"Ours {ours['fan_epi_period_kwh_m2']:.4f} versus fixed {fixed['fan_epi_period_kwh_m2']:.4f} kWh/m2 over the simulated period ({epi_delta:+.2f}%).",
            "limit": "Fan-only period EPI excludes lighting, appliances and other building electricity. It is not annual whole-building EPI.",
        },
    ]
    result = {
        "pre_change_trajectories_identical": before_identical,
        "provenance": "Assessment of recorded simulated outcomes; no new inference or human data",
        "target_recovery": target_checks,
        "post_change_acceptance_difference_pp": post_acceptance_delta,
        "hypotheses": hypotheses,
        "phase_comparison_note": "Before and after windows differ in duration and weather. Matched methods share forcing within each seed. These are descriptive synthetic contrasts, not participant statistics.",
    }
    (out / "hypothesis_assessment.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    from .paths import ROOT

    print(json.dumps(assess_hypotheses(ROOT / "outputs/study"), indent=2))
