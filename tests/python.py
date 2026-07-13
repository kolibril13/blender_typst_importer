"""Run Blender's bundled Python with arguments passed after ``--``.

The GitHub workflow uses this script to install the project and its test
dependencies into the same Python environment that later imports ``bpy``.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import traceback


def _arguments_after_blender_separator() -> list[str]:
    try:
        separator = sys.argv.index("--")
    except ValueError as exc:
        raise SystemExit("Expected Python arguments after Blender's '--' separator") from exc
    return sys.argv[separator + 1 :]


def main() -> None:
    arguments = _arguments_after_blender_separator()
    if not arguments:
        raise SystemExit("No Python arguments were supplied")

    project_root = Path(__file__).resolve().parents[1]
    python_executable = os.path.realpath(sys.executable)
    subprocess.run(
        [python_executable, *arguments],
        cwd=project_root,
        check=True,
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
    except BaseException:
        traceback.print_exc()
        raise SystemExit(1)
