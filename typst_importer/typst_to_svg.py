from pathlib import Path
import tempfile

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

    # Create a temporary SVG file path
    temp_dir = Path(tempfile.gettempdir())
    svg_file_name = f"{file_name_without_ext}.svg"
    svg_file = temp_dir / svg_file_name
    # Compile the input file to an SVG via Typst
    typst.compile(typst_file, format="svg", output=str(svg_file))

    step1_content = svg_file.read_text()
    step3_content = preprocess_svg(step1_content)

    svg_file3 = temp_dir / "step3.svg"
    svg_file3.write_text(step3_content)
    # Import the generated SVG into Blender
    bpy.ops.import_curve.svg(filepath=str(svg_file3))

    imported_collection = bpy.context.scene.collection.children.get(svg_file3.name)
    imported_collection.name = f"Typst_{file_name_without_ext}"
    imported_collection.processed_svg = step3_content

    for obj in imported_collection.objects:
        obj.data.transform(Matrix.Scale(scale_factor, 4))

    if join_curves and len(imported_collection.objects) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in imported_collection.objects:
            obj.select_set(True)
        # Set the first curve as the active object
        bpy.context.view_layer.objects.active = imported_collection.objects[0]
        bpy.ops.object.join()
        # Rename the joined object
        bpy.context.active_object.name = file_name_without_ext

    if origin_to_char:
        bpy.ops.object.select_all(action="DESELECT")
        if imported_collection.objects:
            # Set the first object as active
            bpy.context.view_layer.objects.active = imported_collection.objects[0]
            # Now we can safely set the mode to OBJECT
            bpy.ops.object.mode_set(mode="OBJECT")
            for obj in imported_collection.objects:
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")
                obj.select_set(False)

    if convert_to_mesh:
        for obj in imported_collection.objects:
            if obj.type == "CURVE":
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                bpy.ops.object.convert(target="MESH")
                obj.select_set(False)

    return imported_collection


def typst_express(
    content: str,
    name: str = "typst_expr",
    header: str = "",
    scale_factor: float = 100.0,
    origin_to_char: bool = False,
    join_curves: bool = False,
    convert_to_mesh: bool = False,
) -> bpy.types.Collection:
    """
    A function to create Blender curves from Typst content.

    Args:
        content (str): The main Typst content/body to be rendered
        name (str, optional): Name for the generated collection. Defaults to "typst_expr".
        header (str, optional): Typst header content with settings. If not provided,
                              uses default settings for auto-sizing and text size.
        scale_factor (float, optional): Scale factor for the imported curves. Defaults to 100.0.
        origin_to_char (bool, optional): If True, set the origin of each object to its geometry. Defaults to False.
        join_curves (bool, optional): If True, join all curves into a single object. Defaults to False.
        convert_to_mesh (bool, optional): If True, convert curves to meshes. Defaults to False.

    Returns:
        bpy.types.Collection: The collection of imported Blender curves.
    """

    # Default header if none provided
    default_header = """
#set page(width: auto, height: auto, margin: 0cm, fill: none)
#set text(size: 50pt)
"""
    # Use provided header or default
    header_content = header if header else default_header

    # Create temporary file with the specified name
    temp_file = Path(tempfile.gettempdir()) / f"{name}.typ"

    # Write content to temporary file
    temp_file.write_text(header_content + content)

    # Use existing function to convert to Blender curves
    collection = typst_to_blender_curves(
        temp_file, scale_factor, origin_to_char, join_curves, convert_to_mesh
    )

    # Rename the collection to the specified name
    collection.name = name

    return collection
