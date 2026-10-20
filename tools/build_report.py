"""Rebuild the final submission PDF from completed study evidence."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hostel_cooling.pdf_report import build_report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "outputs/study"))
    args = parser.parse_args()
    print(build_report(args.output))
