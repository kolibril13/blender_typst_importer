"""Run pytest inside Blender, forwarding arguments passed after ``--``."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import traceback


def _pytest_arguments() -> list[str]:
    try:
        separator = sys.argv.index("--")
    except ValueError:
        return []
    return sys.argv[separator + 1 :]


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    os.chdir(project_root)
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    import pytest

    raise SystemExit(pytest.main(_pytest_arguments()))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        # Blender otherwise reports a script exception but still exits zero,
        # which would turn import/collection failures into green CI runs.
        traceback.print_exc()
        raise SystemExit(1)
