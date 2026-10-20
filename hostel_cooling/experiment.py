"""Seeded, closed-loop synthetic experiments. Never evidence of measured savings."""
import csv
import json
import math
import random
import statistics
import time
from dataclasses import replace
from pathlib import Path
from .domain import Action, Conditions, Preference, Room
from .ann import ComfortANN
from .comfort import simulated_response
from .physics import step
from .policies import METHODS, choose
from .llm import Offline


def weather(days, seed, dt_minutes=15):
    rng = random.Random(seed)
    output = []
    for i in range(days*96):
        hour = (i % 96)/4
        day = i//96
        outdoor = 29.5 + 5*math.sin((hour-9)*math.pi/12) + 1.2*math.sin(day*.9) + rng.gauss(0, .25)
        rh = max(20, min(90, 52-20*math.sin((hour-9)*math.pi/12)+rng.gauss(0, 2)))
        activity = "sleep" if hour < 7 or hour >= 23 else "away" if 9 <= hour < 17 else "study"
        output.append(Conditions(outdoor_c=outdoor, outdoor_rh=rh, solar_w_m2=max(0, 720*math.sin((hour-6)*math.pi/12)),
            wind_ms=max(.1, 1.5+rng.gauss(0, .4)), hour=hour, activity=activity,
            running_mean_c=29.5, rain=(day % 4 == 2 and 17 <= hour < 18)))
    return output


def run_experiment(output_dir, days=7, seeds=(11, 23, 47), llm=None):
    if not 1 <= days <= 60 or not seeds:
        raise ValueError("days must be 1..60 and at least one seed is required")
    if len(set(seeds)) != len(seeds):
        raise ValueError("Use distinct weather seeds; repeated seeds are not independent runs")
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    room = Room()
    ann = ComfortANN()
    backend = llm or Offline()
    methods = [m for m in METHODS if m != "generic_llm" or backend.is_llm]
    skipped = [] if backend.is_llm else [{"method": "generic_llm", "reason": "No real LLM configured. Offline rules are not a generic LLM baseline."}]
    runs, trajectory, evidence = [], [], []
    for seed in seeds:
        forcing = weather(days, seed)
        # Explicit simulated survey targets are shared with ours and survey ablation.
        initial_target = 28 + random.Random(seed+913).choice((-.5, 0, .5))
        survey = Preference(target_c=initial_target, activity_targets={"study": initial_target, "sleep": initial_target-.5}, study_airflow=True)
        for method in methods:
            p = survey.patched({}) if method in ("ours", "survey") else Preference()
            hidden = survey.patched({})
            current = Action(); state = replace(forcing[0], indoor_c=29, rh=55)
            energy, votes, violations, acceptances, latency, gaps = 0, [], 0, [], [], []
            adaptive_count, occupied_count = 0, 0
            error_message = None
            method_trajectory = []
            for i, weather_row in enumerate(forcing):
                c = replace(weather_row, indoor_c=state.indoor_c, rh=state.rh)
                # Mid-trial shift: identical hidden target change for every policy.
                # Conversation is an explicit observation, not a target read from the oracle.
                change_step = (days//2)*96 + 17*4
                if i == change_step:
                    hidden = hidden.patched({"activity_targets": {"study": initial_target-1}})
                    if method == "ours":
                        message = f"I prefer {initial_target-1} C when studying. I want airflow."
                        started = time.perf_counter()
                        try:
                            patch = backend.extract(message, "study", p)
                            p = p.patched(patch)
                        except Exception as error:
                            error_message = str(error); break
                        evidence.append({"seed": seed, "step": i, "provenance": "synthetic scripted conversation", "message": message,
                                         "patch": patch, "backend": backend.name, "extraction_ms": (time.perf_counter()-started)*1000})
                started = time.perf_counter()
                try:
                    action, info = choose(method, room, c, p, current, ann, backend, seed=seed*10000+i)
                except Exception as error:
                    error_message = str(error); break
                latency.append((time.perf_counter()-started)*1000)
                state, heat = step(room, c, action)
                energy += heat["fan_wh"]
                vote, accepted = simulated_response(state, room, action, hidden)
                if c.activity != "away":
                    occupied_count += 1
                    votes.append(vote); violations += abs(vote) > 1
                    acceptances.append(accepted)
                    adaptive_count += bool(info.get("adaptive_applicable"))
                if info.get("exact_gap") is not None:
                    gaps.append(info["exact_gap"])
                method_trajectory.append({"provenance": "synthetic", "seed": seed, "method": method, "step": i, "day": i//96+1,
                    "hour": c.hour, "activity": c.activity, "outdoor_c": c.outdoor_c, "indoor_c": state.indoor_c,
                    "rh": state.rh, **action.dict(), "fan_wh": heat["fan_wh"], "tsv_simulated": vote if c.activity != "away" else "",
                    "acceptance_proxy": int(accepted) if c.activity != "away" else ""})
                current = action
            if error_message:
                skipped.append({"method": method, "seed": seed, "reason": error_message, "partial_run_discarded": True})
                continue
            trajectory.extend(method_trajectory)
            runs.append({"seed": seed, "method": method, "days": days, "fan_wh_day": energy/days,
                "fan_epi_period_kwh_m2": energy/1000/room.area_m2,
                "mean_abs_tsv_proxy": statistics.mean(abs(v) for v in votes),
                "mean_tsv_proxy": statistics.mean(votes),
                "comfort_violation_pct": 100*violations/occupied_count,
                "acceptance_proxy_pct": 100*statistics.mean(acceptances),
                "controller_latency_ms_median": statistics.median(latency),
                "controller_latency_ms_p95": sorted(latency)[int(.95*(len(latency)-1))],
                "ga_gap_mean": statistics.mean(gaps) if gaps else None,
                "ga_gap_max": max(gaps) if gaps else None,
                "occupied_steps": occupied_count,
                "adaptive_eligible_pct": 100*adaptive_count/occupied_count if method == "adaptive" else None})
    rows = []
    metrics = ("fan_wh_day", "fan_epi_period_kwh_m2", "mean_abs_tsv_proxy", "mean_tsv_proxy", "comfort_violation_pct",
               "acceptance_proxy_pct", "controller_latency_ms_median", "controller_latency_ms_p95")
    for method in methods:
        subset = [r for r in runs if r["method"] == method]
        if not subset:
            continue
        row = {"method": method, "label": METHODS[method], "n_seeds": len(subset)}
        for metric in metrics:
            values = [r[metric] for r in subset]
            row[metric] = statistics.mean(values)
            row[metric+"_sd"] = statistics.stdev(values) if len(values) > 1 else 0
        row["ga_gap_max"] = max((r["ga_gap_max"] for r in subset if r["ga_gap_max"] is not None), default=None)
        rows.append(row)
    fixed = next((r for r in rows if r["method"] == "fixed"), None)
    for row in rows:
        row["fan_energy_change_vs_fixed_pct"] = 100*(row["fan_wh_day"]/fixed["fan_wh_day"]-1) if fixed and fixed["fan_wh_day"] else None
    summary = {"title": "Cooling for student hostels", "provenance": "SYNTHETIC SIMULATION - no human pilot or measured savings",
        "preference_backend": backend.name, "real_llm_used": backend.is_llm, "days_per_seed": days, "seeds": list(seeds),
        "timestep_minutes": 15, "room": room.__dict__, "ann_validation": ann.validation,
        "metrics_scope": "Fan electricity only; EPI is kWh/m2 over the simulated period, not annual whole-building EPI. All policies are auto-applied; acceptance is an oracle proxy, not observed behavior.",
        "rows": rows, "runs": runs, "skipped": skipped,
        "limitations": ["Uncalibrated one-node RC model; facade irradiance and wind-driven ventilation are proxies.",
            "Air temperature approximates operative temperature; no radiant sensor, latent heat coupling or CFD.",
            "ANN trained on synthetic generic occupant labels; no evidence of human generalization.",
            "Comfort and acceptance derive from a related synthetic oracle; favorable results are not independent validation.",
            "Ours and survey start from identical simulated survey data; a scripted preference change tests memory mechanically.",
            "Constant one-hour weather/activity forecast; no guarantee of long-horizon energy optimality.",
            "Adaptive reference excludes sleep and away; expert fallback explicitly handles those periods.",
            "No ASHRAE, GRIHA or LEED certification and no autonomous physical device control."]}
    (out/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out/"conversation_evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    for name, records in (("comparison.csv", rows), ("runs.csv", runs), ("trajectories.csv", trajectory)):
        if records:
            with (out/name).open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    from .report import write_report
    write_report(summary, out)
    return summary
