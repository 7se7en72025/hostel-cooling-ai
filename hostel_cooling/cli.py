import argparse
import json
from pathlib import Path
from .paths import ROOT


def main():
    parser = argparse.ArgumentParser(
        description="Combined CE F417 / CE F423 hostel cooling research system"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Open local advisory dashboard")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--llm", action="store_true")
    serve.add_argument(
        "--backend", choices=["local", "ollama", "offline", "replay"], default="local"
    )
    exp = sub.add_parser(
        "experiment", help="Run reproducible synthetic policy comparison"
    )
    exp.add_argument("--days", type=int, default=7)
    exp.add_argument("--seeds", type=int, nargs="+", default=[11, 23, 47])
    exp.add_argument("--output", default=str(ROOT / "outputs/experiment"))
    exp.add_argument(
        "--llm",
        action="store_true",
        help="Use actual Ollama extraction and B4; many local model requests",
    )
    exp.add_argument(
        "--backend", choices=["local", "ollama", "offline", "replay"], default="local"
    )
    exp.add_argument("--control-minutes", type=int, choices=[15, 30, 60], default=60)
    setup = sub.add_parser(
        "setup-model",
        help="Download and verify the pinned local transformer and portable runtime",
    )
    setup.add_argument("--acceleration", choices=["cpu", "vulkan"], default="vulkan")
    train = sub.add_parser("train", help="Train and save comfort and activity models")
    study = sub.add_parser(
        "study", help="Run the complete simulated study with actual LLM inference"
    )
    study.add_argument("--days", type=int, default=7)
    study.add_argument("--seeds", nargs="+", type=int, default=[11, 23, 47])
    study.add_argument("--output", default=str(ROOT / "outputs/study"))
    study.add_argument(
        "--backend", choices=["local", "ollama", "offline", "replay"], default="local"
    )
    language = sub.add_parser("evaluate-language")
    language.add_argument("--output", default=str(ROOT / "outputs/study"))
    language.add_argument(
        "--backend", choices=["local", "ollama", "offline", "replay"], default="local"
    )
    gen = sub.add_parser("sample-data")
    gen.add_argument("--output", default=str(ROOT / "data/synthetic_pilot.csv"))
    gen.add_argument("--days", type=int, default=7)
    validate = sub.add_parser("validate")
    validate.add_argument("csv")
    cal = sub.add_parser("calibrate")
    cal.add_argument("csv")
    cal.add_argument("--output", default=str(ROOT / "outputs/calibration.json"))
    args = parser.parse_args()
    try:
        if args.command == "serve":
            from .server import serve
            from .llm import get_backend

            serve(args.port, get_backend("ollama" if args.llm else args.backend))
        elif args.command == "experiment":
            from .experiment import run_experiment
            from .llm import get_backend

            result = run_experiment(
                args.output,
                args.days,
                tuple(args.seeds),
                get_backend("ollama" if args.llm else args.backend),
                control_every=args.control_minutes // 15,
            )
            print(
                json.dumps(
                    {
                        "output": str(Path(args.output).resolve()),
                        "methods": len(result["rows"]),
                        "provenance": result["provenance"],
                        "skipped": result["skipped"],
                    },
                    indent=2,
                )
            )
        elif args.command == "sample-data":
            if not 1 <= args.days <= 60:
                raise ValueError("days must be 1..60")
            from .pilot import generate_pilot

            print(
                f"Wrote {generate_pilot(args.output,args.days)} synthetic rows to {args.output}"
            )
        elif args.command == "validate":
            from .pilot import load_pilot

            rows = load_pilot(args.csv)
            print(
                json.dumps({"valid": True, "rows": len(rows), "provenance": rows[0][3]})
            )
        elif args.command == "calibrate":
            from .pilot import calibrate

            print(json.dumps(calibrate(args.csv, args.output), indent=2))
        elif args.command == "setup-model":
            from .local_model import setup

            print(json.dumps(setup(args.acceleration), indent=2))
        elif args.command == "train":
            from .study import train_models

            print(json.dumps(train_models(), indent=2))
        elif args.command == "study":
            from .study import run_study

            result = run_study(args.output, args.days, tuple(args.seeds), args.backend)
            print(
                json.dumps(
                    {
                        "complete": result["complete"],
                        "rows": len(result["rows"]),
                        "skipped": result["skipped"],
                    },
                    indent=2,
                )
            )
        elif args.command == "evaluate-language":
            from .language_evaluation import evaluate_language
            from .llm import get_backend

            result = evaluate_language(get_backend(args.backend), args.output)
            print(
                json.dumps({k: v for k, v in result.items() if k != "cases"}, indent=2)
            )
    except (ValueError, RuntimeError, FileNotFoundError, PermissionError) as error:
        parser.exit(2, f"Error: {error}\n")
