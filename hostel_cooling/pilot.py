"""CSV validation and chronological one-step RC calibration."""

import csv
import json
import math
import random
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from .domain import Action, Conditions, Room, Preference, legal_actions
from .physics import step
from .experiment import weather
from .policies import choose
from .comfort import simulated_response

FIELDS = (
    "timestamp",
    "indoor_c",
    "outdoor_c",
    "rh",
    "outdoor_rh",
    "solar_w_m2",
    "wind_ms",
    "activity",
    "fan",
    "window",
    "curtain",
    "tsv",
    "accepted",
    "consent",
    "provenance",
)


def generate_pilot(path, days=7, seed=101):
    room, p, state, action = Room(), Preference(), None, Action()
    start = datetime(2026, 4, 1)
    rows = []
    for i, forcing in enumerate(weather(days, seed)):
        c = replace(
            forcing,
            indoor_c=state.indoor_c if state else 29,
            rh=state.rh if state else 55,
        )
        action, _ = choose("expert", room, c, p, action)
        vote, accepted = simulated_response(c, room, action, p)
        rows.append(
            {
                "timestamp": (start + timedelta(minutes=15 * i)).isoformat(),
                "indoor_c": c.indoor_c,
                "outdoor_c": c.outdoor_c,
                "rh": c.rh,
                "outdoor_rh": c.outdoor_rh,
                "solar_w_m2": c.solar_w_m2,
                "wind_ms": c.wind_ms,
                "activity": c.activity,
                **action.dict(),
                "tsv": vote if c.activity != "away" else "",
                "accepted": int(accepted) if c.activity != "away" else "",
                "consent": "true",
                "provenance": "synthetic",
            }
        )
        state, _ = step(room, c, action)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def load_pilot(path):
    records = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if set(FIELDS) - set(reader.fieldnames or []):
            raise ValueError(
                "CSV is missing fields: "
                + ", ".join(sorted(set(FIELDS) - set(reader.fieldnames or [])))
            )
        last = None
        for line, row in enumerate(reader, 2):
            try:
                t = datetime.fromisoformat(row["timestamp"])
                if last and (t - last).total_seconds() != 900:
                    raise ValueError(
                        "timestamps must be consecutive 15-minute intervals; split gaps into separate files"
                    )
                if row["consent"].lower() != "true":
                    raise ValueError("consent must be true for every row")
                if row["provenance"] not in ("synthetic", "measured"):
                    raise ValueError("provenance must be synthetic or measured")
                c = Conditions(
                    **{
                        k: float(row[k])
                        for k in (
                            "indoor_c",
                            "outdoor_c",
                            "rh",
                            "outdoor_rh",
                            "solar_w_m2",
                            "wind_ms",
                        )
                    },
                    hour=t.hour + t.minute / 60,
                    activity=row["activity"],
                )
                action = Action(
                    int(row["fan"]), float(row["window"]), int(row["curtain"])
                )
                if row["tsv"]:
                    v = float(row["tsv"])
                    if not math.isfinite(v) or not -3 <= v <= 3:
                        raise ValueError("tsv must be -3..3 or blank")
                if row["accepted"] not in ("0", "1", ""):
                    raise ValueError("accepted must be 0/1 or blank")
                records.append((t, c, action, row["provenance"]))
                last = t
            except (ValueError, TypeError, OverflowError) as error:
                raise ValueError(f"CSV line {line}: {error}") from error
    if len(records) < 12:
        raise ValueError(
            "At least 12 consecutive rows are required; >=7 days recommended for real calibration."
        )
    if len({r[3] for r in records}) != 1:
        raise ValueError(
            "Do not mix synthetic and measured records in one calibration."
        )
    return records


def calibrate(path, output):
    rows = load_pilot(path)
    split = int((len(rows) - 1) * 0.8)

    def rmse(room, low, high):
        errors = []
        for i in range(low, high):
            pred, _ = step(room, rows[i][1], rows[i][2])
            errors.append((pred.indoor_c - rows[i + 1][1].indoor_c) ** 2)
        return math.sqrt(sum(errors) / len(errors))

    candidates = [
        replace(Room(), ua_w_k=ua, capacity_j_k=cap)
        for ua in (20, 30, 40, 45, 50, 60, 80)
        for cap in (500_000, 1_000_000, 1_500_000, 2_000_000, 3_000_000, 4_000_000)
    ]
    best = min(candidates, key=lambda r: rmse(r, 0, split))
    # Refine using training transitions only. Test transitions never select parameters.
    refined = [
        replace(best, ua_w_k=ua, capacity_j_k=cap)
        for ua in range(max(5, int(best.ua_w_k) - 8), int(best.ua_w_k) + 9, 2)
        for cap in range(
            max(250_000, int(best.capacity_j_k) - 500_000),
            int(best.capacity_j_k) + 500_001,
            250_000,
        )
    ]
    best = min([best] + refined, key=lambda r: rmse(r, 0, split))
    test_errors = [
        step(best, rows[i][1], rows[i][2])[0].indoor_c - rows[i + 1][1].indoor_c
        for i in range(split, len(rows) - 1)
    ]
    persistence = math.sqrt(
        sum(
            (rows[i][1].indoor_c - rows[i + 1][1].indoor_c) ** 2
            for i in range(split, len(rows) - 1)
        )
        / len(test_errors)
    )
    result = {
        "provenance": rows[0][3],
        "rows": len(rows),
        "train_transitions": split,
        "test_transitions": len(rows) - 1 - split,
        "split": "chronological 80/20; parameters selected on training only",
        "selected_room": best.__dict__,
        "train_rmse_c": rmse(best, 0, split),
        "test_rmse_c": rmse(best, split, len(rows) - 1),
        "test_mae_c": sum(abs(e) for e in test_errors) / len(test_errors),
        "test_bias_c": sum(test_errors) / len(test_errors),
        "persistence_test_rmse_c": persistence,
        "warning": "One-step temperature fit only. Humidity, fan cooling effect, surface radiation and occupant preferences are not calibrated. Synthetic self-recovery is a software check, not physical validation.",
    }
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def generate_noisy_pilot(path, days=14, seed=301):
    """Independent sensor noise and a plant different from the initial controller model."""
    rng = random.Random(seed)
    true_room = replace(Room(), ua_w_k=58, capacity_j_k=2_500_000)
    start = datetime(2026, 3, 1)
    state = None
    rows = []
    for i, forcing in enumerate(weather(days, seed)):
        c = replace(
            forcing,
            indoor_c=state.indoor_c if state else 29,
            rh=state.rh if state else 55,
        )
        action = rng.choice(legal_actions(c, Preference()))
        vote, accepted = simulated_response(c, true_room, action, Preference())
        rows.append(
            {
                "timestamp": (start + timedelta(minutes=15 * i)).isoformat(),
                "indoor_c": c.indoor_c + rng.gauss(0, 0.12),
                "outdoor_c": c.outdoor_c + rng.gauss(0, 0.08),
                "rh": max(1, min(100, c.rh + rng.gauss(0, 1))),
                "outdoor_rh": c.outdoor_rh,
                "solar_w_m2": max(0, c.solar_w_m2 + rng.gauss(0, 12)),
                "wind_ms": c.wind_ms,
                "activity": c.activity,
                **action.dict(),
                "tsv": vote if c.activity != "away" else "",
                "accepted": int(accepted) if c.activity != "away" else "",
                "consent": "true",
                "provenance": "synthetic",
            }
        )
        state, _ = step(true_room, c, action)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return {
        "plant_room": true_room.__dict__,
        "rows": len(rows),
        "seed": seed,
        "noise": {
            "indoor_temperature_sd_c": 0.12,
            "outdoor_temperature_sd_c": 0.08,
            "rh_sd_pct": 1,
            "solar_sd_w_m2": 12,
        },
        "provenance": "synthetic noisy sensor experiment; not measured data",
    }
