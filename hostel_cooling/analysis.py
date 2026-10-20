"""Paired comparisons and transparent evidence plots for the complete study."""

import csv
import json
import math
import statistics
from pathlib import Path
import numpy as np


def model_figures(model_dir, output_dir):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    model_dir = Path(model_dir)
    output_dir = Path(output_dir)
    loss = json.loads((model_dir / "ann_loss.json").read_text(encoding="utf-8"))
    routine = json.loads(
        (model_dir / "routine_validation.json").read_text(encoding="utf-8")
    )
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5), layout="constrained")
    axes[0].plot([r["epoch"] for r in loss], [r["mse"] for r in loss], color="#287758")
    axes[0].set(
        xlabel="Training epoch", ylabel="Synthetic TSV MSE", title="ANN training curve"
    )
    axes[0].spines[["right", "top"]].set_visible(False)
    matrix = np.asarray(routine["confusion_matrix"])
    axes[1].imshow(matrix, cmap="Greens")
    axes[1].set(
        xticks=range(3),
        yticks=range(3),
        xticklabels=routine["labels"],
        yticklabels=routine["labels"],
        xlabel="Predicted activity",
        ylabel="Synthetic label",
        title="Chronological activity holdout",
    )
    for i in range(3):
        for j in range(3):
            axes[1].text(
                j,
                i,
                str(matrix[i, j]),
                ha="center",
                va="center",
                color="white" if matrix[i, j] > 120 else "#233d33",
            )
    fig.savefig(output_dir / "model_validation.png", dpi=170)
    plt.close(fig)


def analyze_study(output_dir):
    out = Path(output_dir)
    summary = json.loads((out / "summary.json").read_text())
    runs = summary["runs"]
    paired = []
    metrics = (
        "fan_wh_day",
        "comfort_violation_pct",
        "mean_abs_tsv_proxy",
        "acceptance_proxy_pct",
    )
    ours = {r["seed"]: r for r in runs if r["method"] == "ours"}
    for method in dict.fromkeys(r["method"] for r in runs):
        if method == "ours":
            continue
        reference = {r["seed"]: r for r in runs if r["method"] == method}
        seeds = sorted(set(ours) & set(reference))
        for metric in metrics:
            differences = [ours[s][metric] - reference[s][metric] for s in seeds]
            if not differences:
                continue
            n = len(differences)
            mean = statistics.mean(differences)
            sd = statistics.stdev(differences) if n > 1 else None
            critical = {
                1: 12.706,
                2: 4.303,
                3: 3.182,
                4: 2.776,
                5: 2.571,
                6: 2.447,
                7: 2.365,
                8: 2.306,
                9: 2.262,
            }.get(n - 1, 1.96)
            margin = critical * sd / math.sqrt(n) if sd is not None else None
            paired.append(
                {
                    "contrast": "ours minus " + method,
                    "metric": metric,
                    "n_weather_seeds": n,
                    "mean_delta": mean,
                    "sd_delta": sd,
                    "ci95_low": mean - margin if margin is not None else None,
                    "ci95_high": mean + margin if margin is not None else None,
                    "interpretation": "Exploratory paired weather-seed t interval; not a participant effect or human study.",
                }
            )
    (out / "paired_comparisons.json").write_text(
        json.dumps(paired, indent=2), encoding="utf-8"
    )
    with (out / "paired_comparisons.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=paired[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(paired)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = []
    with (out / "trajectories.csv").open(newline="", encoding="utf-8") as stream:
        data = list(csv.DictReader(stream))
    seed = summary["seeds"][0]
    fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True, layout="constrained")
    for method, color in [
        ("fixed", "#a3a9ac"),
        ("generic_llm", "#c18a45"),
        ("ours", "#287758"),
    ]:
        points = [r for r in data if r["method"] == method and int(r["seed"]) == seed]
        if not points:
            continue
        x = [float(r["step"]) / 4 / 24 for r in points]
        axes[0].plot(
            x, [float(r["indoor_c"]) for r in points], label=method, color=color, lw=1
        )
        axes[1].plot(
            x,
            np.cumsum([float(r["fan_wh"]) for r in points]) / 1000,
            label=method,
            color=color,
        )
        axes[2].plot(
            x,
            [
                float(r["tsv_simulated"]) if r["tsv_simulated"] else np.nan
                for r in points
            ],
            color=color,
            lw=0.7,
        )
    for ax in axes:
        ax.spines[["right", "top"]].set_visible(False)
        ax.grid(alpha=0.15)
    axes[0].set_ylabel("Indoor air / C")
    axes[0].legend(ncol=3, frameon=False)
    axes[1].set_ylabel("Fan energy / kWh")
    axes[2].set_ylabel("Synthetic TSV")
    axes[2].set_xlabel("Simulated day")
    axes[2].axhline(1, color="gray", ls="--", lw=0.5)
    axes[2].axhline(-1, color="gray", ls="--", lw=0.5)
    fig.suptitle(
        f"Closed-loop trajectories | seed {seed} | synthetic plant, actual local LLM",
        fontsize=12,
    )
    fig.savefig(out / "trajectories.png", dpi=170)
    plt.close(fig)
    if summary.get("calibration"):
        cal = summary["calibration"]
        fig, ax = plt.subplots(figsize=(6, 3), layout="constrained")
        ax.bar(
            ["Calibrated RC", "Persistence"],
            [cal["test_rmse_c"], cal["persistence_test_rmse_c"]],
            color=["#287758", "#adb9b0"],
        )
        ax.set(
            ylabel="Held-out one-step RMSE / C",
            title="Noisy synthetic pilot: chronological holdout",
        )
        ax.spines[["right", "top"]].set_visible(False)
        fig.savefig(out / "calibration.png", dpi=170)
        plt.close(fig)
    return paired


def sensitivity(output_dir, backend, room, plant_room, ann):
    from .experiment import run_experiment

    out = Path(output_dir)
    records = []
    for weight in (0, 0.1, 0.25, 0.5, 1, 2):
        result = run_experiment(
            out / "sensitivity" / str(weight).replace(".", "_"),
            days=3,
            seeds=(11, 23, 47),
            llm=backend,
            control_every=4,
            room=room,
            plant_room=plant_room,
            methods=["ours"],
            ann=ann,
            preference_overrides={"energy_weight": weight},
        )
        row = result["rows"][0]
        records.append(
            {
                "energy_weight": weight,
                "fan_wh_day": row["fan_wh_day"],
                "mean_abs_tsv_proxy": row["mean_abs_tsv_proxy"],
                "comfort_violation_pct": row["comfort_violation_pct"],
                "acceptance_proxy_pct": row["acceptance_proxy_pct"],
            }
        )
    (out / "sensitivity.json").write_text(
        json.dumps(records, indent=2), encoding="utf-8"
    )
    with (out / "sensitivity.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=records[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
    ax.plot(
        [r["fan_wh_day"] for r in records],
        [r["mean_abs_tsv_proxy"] for r in records],
        "o-",
        color="#287758",
    )
    for row in records:
        ax.annotate(
            f'w={row["energy_weight"]}',
            (row["fan_wh_day"], row["mean_abs_tsv_proxy"]),
            xytext=(5, 6),
            textcoords="offset points",
            fontsize=8,
        )
    ax.set(
        xlabel="Fan Wh/day",
        ylabel="Mean absolute synthetic TSV",
        title="Objective-weight sensitivity | same synthetic scenario distribution",
    )
    ax.spines[["right", "top"]].set_visible(False)
    fig.savefig(out / "sensitivity.png", dpi=170)
    plt.close(fig)
    return records
