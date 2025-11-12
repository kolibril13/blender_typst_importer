import sys

from pathlib import Path


ADDON_DIR = Path(__file__).resolve().parent


def add_current_module_to_path():
    path = str(ADDON_DIR.parent)
    sys.path.append(path)
