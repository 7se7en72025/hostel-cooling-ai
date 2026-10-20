"""Package the final report, editable presentation, viva guide and complete source."""

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/study"
PREFIX = "Hostel_Cooling_Submission/"


def verify(path):
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read(PREFIX + "MANIFEST.json"))
        for entry in manifest["files"]:
            data = archive.read(PREFIX + entry["path"])
            if (
                len(data) != entry["bytes"]
                or hashlib.sha256(data).hexdigest() != entry["sha256"]
            ):
                raise ValueError("Archive integrity mismatch: " + entry["path"])
        print(
            json.dumps(
                {
                    "status": "passed",
                    "files_verified": len(manifest["files"]),
                    "path": str(Path(path).resolve()),
                },
                indent=2,
            )
        )
    return manifest


def build(target):
    main = {
        "01_Final_Report.pdf": OUT / "Hostel_Cooling_Project_Report.pdf",
        "02_Editable_Presentation.pptx": OUT / "Hostel_Cooling_Final_Presentation.pptx",
        "03_Presentation.pdf": OUT / "Hostel_Cooling_Final_Presentation.pdf",
        "04_Viva_Guide.pdf": OUT / "Hostel_Cooling_Viva_Guide.pdf",
    }
    for path in main.values():
        if not path.is_file():
            raise ValueError("Final deliverable missing: " + str(path))
    paths = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
        )
        .decode("utf-8")
        .split("\0")
    )
    files = dict(main)
    for name in sorted(set(paths)):
        if not name or name.startswith(
            ("outputs/demo/", "runtime/", "build/", "dist/", ".venv/")
        ):
            continue
        if name == "outputs/study/submission_manifest.json":
            continue
        path = ROOT / name
        if path.is_file():
            files["05_Source_Code/" + name] = path
    readme = (
        "HOSTEL COOLING / CE F417 + CE F423 / FINAL SUBMISSION\n\n"
        "01_Final_Report.pdf: 14-page course report with all eight hypothesis findings.\n"
        "02_Editable_Presentation.pptx: 18 slides, native editable charts/tables, speaker notes.\n"
        "03_Presentation.pdf: rendered copy for reliable presentation without PowerPoint.\n"
        "04_Viva_Guide.pdf: 34 questions, answers, key numbers and reproduction commands.\n"
        "05_Source_Code/: complete source, trained small models, data and raw study evidence.\n\n"
        "Start the application from 05_Source_Code using start.bat on the prepared machine.\n"
        "For a fresh Windows machine, install Python 3.11+ and run setup.bat once, then start.bat.\n"
        "Setup downloads the pinned approximately 2.5 GB local Qwen model and runtime.\n"
        "Large binaries, model weights and private participant records are excluded from this ZIP.\n\n"
        "Read outputs/study/ inside 05_Source_Code for 27 runs, 18,144 intervals, actual\n"
        "inference journals, held-out language outcomes, calibration and verification records.\n"
        "Room and occupant outcomes are simulated; inference and software computations actually ran.\n"
        "Energy falls with a comfort trade-off. No measured human effectiveness is claimed.\n\n"
        "Reproduce frozen results without new inference:\n"
        "  python -m hostel_cooling study --backend replay --output build/replay-study\n"
        "  python tools/verify_replay.py\n\n"
        "Rebuild editable slides/viva after installing requirements-submission.txt:\n"
        "  python tools/build_presentation.py\n"
        "  python tools/build_viva.py\n"
        "For the slide PDF, export the PPTX using PowerPoint or LibreOffice.\n\n"
        "MANIFEST.json records every included file's SHA256. Verify this ZIP with:\n"
        "  python tools/build_submission.py --verify PATH_TO_ZIP\n"
    ).encode("utf-8")
    data = {name: path.read_bytes() for name, path in files.items()}
    data["START_HERE.txt"] = readme
    manifest = {
        "title": "Hostel cooling: final combined course submission",
        "scope": "Approved simulated computational project; actual local transformer and trained software artifacts",
        "deliverables": {
            "report_pages": 14,
            "editable_slides": 18,
            "viva_questions": 34,
        },
        "files": [
            {
                "path": name,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for name, content in sorted(data.items())
        ],
    }
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name, content in sorted(data.items()):
            archive.writestr(PREFIX + name, content)
        archive.writestr(
            PREFIX + "MANIFEST.json", json.dumps(manifest, indent=2).encode("utf-8")
        )
    verify(target)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT.parent / "Hostel_Cooling_Final_Submission.zip",
    )
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    verify(args.verify) if args.verify else build(args.output)
