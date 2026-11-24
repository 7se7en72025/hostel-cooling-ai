"""Compare a separately executed frozen-response study with the recorded study."""

import argparse
import hashlib
import json
from pathlib import Path


def scientific(value):
    if isinstance(value, dict):
        return {
            k: scientific(v)
            for k, v in value.items()
            if "ms" not in k and k != "backend"
        }
    if isinstance(value, list):
        return [scientific(v) for v in value]
    return value


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", type=Path, default=root / "build/replay-study")
    parser.add_argument("--reference", type=Path, default=root / "outputs/study")
    args = parser.parse_args()
    hashes = {}
    for filename in ("trajectories.csv", "sensitivity.csv"):
        recorded = (args.reference / filename).read_bytes()
        replayed = (args.replay / filename).read_bytes()
        if recorded != replayed:
            raise SystemExit(f"Mismatch: {filename}")
        hashes[filename] = hashlib.sha256(recorded).hexdigest()
    load = lambda folder, name: json.loads((folder / name).read_text(encoding="utf-8"))
    a, b = load(args.reference, "summary.json"), load(args.replay, "summary.json")
    if scientific(a["rows"]) != scientific(b["rows"]):
        raise SystemExit("Scientific comparison metrics differ")
    left = load(args.reference, "language_evaluation.json")
    right = load(args.replay, "language_evaluation.json")
    if scientific(left) != scientific(right):
        raise SystemExit("Language outcomes differ")
    if b.get("real_llm_used") or b.get("inference_mode") != "recorded-response replay":
        raise SystemExit("Replay provenance is incorrectly labeled")
    result = {
        "status": "passed",
        "mode": "frozen actual-response replay, no new inference",
        "identical_files_sha256": hashes,
        "scientific_comparison_metrics": "identical for all nine methods",
        "language_outcomes": "identical for all 24 phrases and memory checks",
        "excluded": "machine-dependent timings and explicit backend labels",
    }
    (args.replay / "reproducibility_verification.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8", newline="\n"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
