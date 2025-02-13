from pathlib import Path
import tempfile
from typing import Optional

from mathutils import Matrix
import bpy
import typst
from .svg_preprocessing import preprocess_svg

# Register the property for collections
bpy.types.Collection.processed_svg = bpy.props.StringProperty(
    name="Processed SVG",
    description="Processed SVG content from Typst",
)


def typst_to_blender_curves(
    typst_file: Path,
    scale_factor: float = 100.0,
    origin_to_char: bool = False,
    join_curves: bool = False,
    convert_to_mesh: bool = False,
) -> bpy.types.Collection:
    """
    Compile a .txt or .typ file to an SVG using Typst,
    then import the generated SVG into Blender.

    Args:
        typst_file (Path): The path to the .txt or .typ file.
        scale_factor (float, optional): Scale factor for the imported curves. Defaults to 100.0.
        origin_to_char (bool, optional): If True, set the origin of each object to its geometry. Defaults to False.
        join_curves (bool, optional): If True, join all curves into a single object. Defaults to False.
        convert_to_mesh (bool, optional): If True, convert curves to meshes. Defaults to False.

    Returns:
        bpy.types.Collection: The collection of imported Blender curves.
    """
    file_name_without_ext = typst_file.stem

    # Create temporary files
    temp_dir = Path(tempfile.gettempdir())
    svg_file = temp_dir / f"{file_name_without_ext}.svg"

    # Compile the input file to an SVG via Typst
    typst.compile(typst_file, format="svg", output=str(svg_file))

    # Process SVG content
    svg_content = svg_file.read_text()
    processed_svg = preprocess_svg(svg_content)

    processed_svg_file = temp_dir / "processed.svg"
    processed_svg_file.write_text(processed_svg)

    # Import the processed SVG into Blender
    bpy.ops.import_curve.svg(filepath=str(processed_svg_file))

    # Get and rename the imported collection
    imported_collection = bpy.context.scene.collection.children.get(
        processed_svg_file.name
    )
    if not imported_collection:
        raise RuntimeError("Failed to import SVG file")

    imported_collection.name = f"Typst_{file_name_without_ext}"
    imported_collection.processed_svg = processed_svg

    # Scale the imported curves
    for obj in imported_collection.objects:
        obj.data.transform(Matrix.Scale(scale_factor, 4))

    if join_curves and len(imported_collection.objects) > 1:
        _join_curves(imported_collection, file_name_without_ext)

    if origin_to_char:
        _set_origins_to_geometry(imported_collection)

    if convert_to_mesh:
        _convert_to_meshes(imported_collection)

    return imported_collection


def _join_curves(collection: bpy.types.Collection, name: str) -> None:
    """Helper function to join curves in a collection."""
    bpy.ops.object.select_all(action="DESELECT")
    for obj in collection.objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = collection.objects[0]
    bpy.ops.object.join()
    bpy.context.active_object.name = name


def _set_origins_to_geometry(collection: bpy.types.Collection) -> None:
    """Helper function to set object origins to geometry."""
    bpy.ops.object.select_all(action="DESELECT")
    if not collection.objects:
        return

    bpy.context.view_layer.objects.active = collection.objects[0]
    bpy.ops.object.mode_set(mode="OBJECT")

    for obj in collection.objects:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")
        obj.select_set(False)


def _convert_to_meshes(collection: bpy.types.Collection) -> None:
    """Helper function to convert curves to meshes."""
    for obj in collection.objects:
        if obj.type != "CURVE":
            continue

        curve_data = obj.data
        original_name = obj.name.replace("Curve", "")

        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        bpy.ops.object.convert(target="MESH")

        new_name = f"Mesh{original_name}"
        obj.name = new_name
        obj.data.name = new_name

        obj.select_set(False)
        bpy.data.curves.remove(curve_data)


def typst_express(
    content: str,
    name: str = "typst_expr",
    header: Optional[str] = None,
    scale_factor: float = 100.0,
    origin_to_char: bool = False,
    join_curves: bool = False,
    convert_to_mesh: bool = False,
) -> bpy.types.Collection:
    """
    Create Blender curves from Typst content.

    Args:
        content (str): The main Typst content/body to be rendered
        name (str, optional): Name for the generated collection. Defaults to "typst_expr".
        header (Optional[str], optional): Typst header content with settings. If None,
                                        uses default settings for auto-sizing and text size.
        scale_factor (float, optional): Scale factor for the imported curves. Defaults to 100.0.
        origin_to_char (bool, optional): If True, set the origin of each object to its geometry. Defaults to False.
        join_curves (bool, optional): If True, join all curves into a single object. Defaults to False.
        convert_to_mesh (bool, optional): If True, convert curves to meshes. Defaults to False.

    Returns:
        bpy.types.Collection: The collection of imported Blender curves.
    """
    default_header = """
#set page(width: auto, height: auto, margin: 0cm, fill: none)
#set text(size: 50pt)
"""
    header_content = header if header is not None else default_header

    # Create and write to temporary file
    temp_file = Path(tempfile.gettempdir()) / f"{name}.typ"
    temp_file.write_text(header_content + content)

    # Convert to Blender curves
    collection = typst_to_blender_curves(
        temp_file, scale_factor, origin_to_char, join_curves, convert_to_mesh
    )
    collection.name = name

    return collection
