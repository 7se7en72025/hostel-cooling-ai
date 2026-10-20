"""Learned activity priors from observed time/activity pairs, with uncertainty."""

import json
import random
from pathlib import Path
import numpy as np

ACTIVITIES = ("study", "sleep", "away")


class RoutineModel:
    def __init__(self, counts=None):
        self.counts = (
            np.zeros((2, 96, 3)) if counts is None else np.asarray(counts, dtype=float)
        )
        if (
            self.counts.shape != (2, 96, 3)
            or not np.isfinite(self.counts).all()
            or (self.counts < 0).any()
        ):
            raise ValueError("Invalid routine model counts")

    def observe(self, hour, weekday, activity):
        if not 0 <= hour < 24 or weekday not in range(7) or activity not in ACTIVITIES:
            raise ValueError("Invalid routine observation")
        self.counts[
            int(weekday >= 5), int(hour * 4) % 96, ACTIVITIES.index(activity)
        ] += 1

    def predict(self, hour, weekday=0):
        if not 0 <= hour < 24 or weekday not in range(7):
            raise ValueError("hour must be 0..24 and weekday 0..6")
        index = int(hour * 4) % 96
        weekend = int(weekday >= 5)
        weights = self.counts[weekend, index].copy()
        weights += 0.25 * (
            self.counts[weekend, (index - 1) % 96]
            + self.counts[weekend, (index + 1) % 96]
        )
        weights += 0.15 * self.counts[1 - weekend, index]
        probabilities = (weights + 0.5) / (weights.sum() + 1.5)
        choice = int(np.argmax(probabilities))
        return {
            "activity": ACTIVITIES[choice],
            "confidence": float(probabilities[choice]),
            "probabilities": dict(zip(ACTIVITIES, map(float, probabilities))),
            "observations": int(self.counts.sum()),
            "uncertain": bool(probabilities[choice] < 0.6),
        }

    def save(self, path, metadata=None):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            json.dumps(
                {"counts": self.counts.tolist(), "metadata": metadata or {}}, indent=2
            ),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8"))["counts"])


def train_synthetic_routines(output_dir, seed=801):
    import csv

    rng = random.Random(seed)
    rows = []
    for day in range(21):
        weekday = day % 7
        wake = 7 + rng.choice((-0.5, 0, 0.5))
        away_start = 9 + rng.choice((-0.5, 0, 0.5))
        away_end = 17 + rng.choice((-0.5, 0, 0.5))
        bed = 23 + rng.choice((-0.5, 0, 0.5))
        for index in range(96):
            hour = index / 4
            activity = (
                "sleep"
                if hour < wake or hour >= bed
                else "away" if away_start <= hour < away_end else "study"
            )
            if weekday >= 5 and activity == "away" and hour < 13:
                activity = "study"
            rows.append(
                {
                    "day": day + 1,
                    "weekday": weekday,
                    "hour": hour,
                    "activity": activity,
                    "split": "train" if day < 14 else "test",
                    "provenance": "synthetic",
                }
            )
    model = RoutineModel()
    for row in rows:
        if row["split"] == "train":
            model.observe(row["hour"], row["weekday"], row["activity"])
    test = [r for r in rows if r["split"] == "test"]
    confusion = np.zeros((3, 3), dtype=int)
    for row in test:
        pred = model.predict(row["hour"], row["weekday"])["activity"]
        confusion[ACTIVITIES.index(row["activity"]), ACTIVITIES.index(pred)] += 1
    f1 = []
    for i in range(3):
        tp = confusion[i, i]
        fp = confusion[:, i].sum() - tp
        fn = confusion[i, :].sum() - tp
        f1.append(float(2 * tp / (2 * tp + fp + fn)))
    result = {
        "provenance": "synthetic schedule learning; no real student routines",
        "seed": seed,
        "train_days": 14,
        "test_days": 7,
        "test_n": len(test),
        "accuracy": float(np.trace(confusion) / confusion.sum()),
        "macro_f1": sum(f1) / 3,
        "labels": ACTIVITIES,
        "confusion_matrix": confusion.tolist(),
        "majority_baseline_accuracy": max(
            sum(r["activity"] == a for r in test) for a in ACTIVITIES
        )
        / len(test),
    }
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "routine_dataset.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    model.save(out / "routine_model.json", result)
    (out / "routine_validation.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result
