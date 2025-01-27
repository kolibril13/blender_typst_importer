# this is 100% identical to utils.py in csv_importer https://github.com/kolibril13/blender_csv_import/blob/main/csv_importer/utils.py
import os
import sys
import numpy as np

from pathlib import Path
from math import floor
from mathutils import Matrix

ADDON_DIR = Path(__file__).resolve().parent


def add_current_module_to_path():
    path = str(ADDON_DIR.parent)
    sys.path.append(path)