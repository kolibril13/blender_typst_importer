from pathlib import Path
import polars as pl
from bpy.types import Object
from .parsers import polars_df_to_bob
from . import addon


def load_typst(filepath: str) -> Object:
    """Load a Typst file and create a Blender object from it.
    
    Args:
        filepath: Path to the Typst file
        
    Returns:
        The created Blender object
    """
    print(f"Loading Typst file: {filepath}")
    # Use the selected/dropped file path
    typst_file = Path(filepath)
    file_name_without_ext = typst_file.stem

    df = pl.read_csv(typst_file)
    bob = polars_df_to_bob(df, name=f"Typst_{file_name_without_ext}")
    try:
        bob.object.csv.filepath = str(typst_file)
    except AttributeError:
        addon.register()
        bob.object.csv.filepath = str(typst_file)

    return bob.object
