"""One workspace convention for source checkouts and installed distributions."""

import os
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(
    os.environ.get(
        "COOLING_WORKSPACE",
        (
            SOURCE_ROOT
            if (SOURCE_ROOT / "pyproject.toml").exists()
            else Path.home() / ".hostel-cooling"
        ),
    )
).resolve()
