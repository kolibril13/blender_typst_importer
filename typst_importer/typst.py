from pathlib import Path
import polars as pl
from bpy.types import Object
from .parsers import polars_df_to_bob
from . import addon
import tempfile
import typst
import bpy

def load_typst(filepath: str) -> Object:
    """Load a Typst file and create a Blender object from it.
    
    Args:
        filepath: Path to the Typst file
        
    Returns:
        The created Blender object
    """
    print(f"Loading Typst file: {filepath}")

    temp_dir = Path(tempfile.gettempdir())
    typst_file = temp_dir / "hello.typ"
    svg_file = temp_dir / "hello.svg"

    # Use the selected/dropped file path
    typst_file = Path(filepath)
    file_name_without_ext = typst_file.stem



    file_content = """
    #set page(width: auto, height: auto, margin: 0cm, fill: none)
    #set text(size: 5000pt)
    $ sum_(k=1)^n k = (n(n+1)) / 2 $
    """
    typst_file.write_text(file_content)
    typst.compile(typst_file, format="svg", output=str(svg_file))

    bpy.ops.import_curve.svg(filepath=str(svg_file))
    col = bpy.context.scene.collection.children['hello.svg']
    col.name = "Formula"




    # df = pl.read_csv(typst_file)
    # bob = polars_df_to_bob(df, name=f"Typst_{file_name_without_ext}")
    # try:
    #     bob.object.csv.filepath = str(typst_file)
    # except AttributeError:
    #     addon.register()
    #     bob.object.csv.filepath = str(typst_file)

    # return bob.object

