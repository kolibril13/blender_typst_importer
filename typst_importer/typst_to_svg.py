import contextlib
from pathlib import Path
import tempfile
from typing import Optional, Tuple

from mathutils import Matrix
import bpy
import typst
import databpy as db

from .node_groups import (
    DEFAULT_GREASE_PENCIL_STROKE_RADIUS,
    add_grease_pencil_stroke_radius_modifier,
)
from .svg_preprocessing import preprocess_svg

# Register the property for collections
bpy.types.Collection.processed_svg = bpy.props.StringProperty(
    name="Processed SVG",
    description="Processed SVG content from Typst",
)

# Store the most recently generated processed SVG on the scene for easy export
bpy.types.Scene.typst_last_processed_svg = bpy.props.StringProperty(
    name="Last Processed SVG",
    description="Most recently generated processed SVG from Typst",
)



def move_objects(objs, target_collection: bpy.types.Collection) -> None:
    """Move one or many objects into a target collection.

    objs: list[bpy.types.Object] or a single object
    """

    # Allow single object
    if isinstance(objs, bpy.types.Object):
        objs = [objs]

    for obj in objs:
        # Unlink from all current collections
        for c in obj.users_collection:
            c.objects.unlink(obj)

        # Link to target collection
        target_collection.objects.link(obj)
        

# Core object and material setup functions
def setup_object(obj: bpy.types.Object, scale_factor: float = 200) -> None:
    """Setup individual object properties."""
    obj.data.transform(Matrix.Scale(scale_factor, 4))
    obj["opacity"] = 1.0
    obj.id_properties_ui("opacity").update(min=0.0, max=1.0, step=0.1)


def create_material(color, name: str = "") -> bpy.types.Material:
    """Create a new material with nodes setup for opacity."""
    # Check if material with this name already exists
    existing_mat = bpy.data.materials.get(name)
    if existing_mat:
        # Blender's native Curve -> Grease Pencil conversion reads the viewport
        # color rather than the shader node color.
        existing_mat.diffuse_color = color
        return existing_mat

    mat = bpy.data.materials.new(name=name)
    # Keep the viewport color in sync with the emission shader. This is also the
    # color used by Blender 5.2 when converting a Curve material to a native
    # Grease Pencil material.
    mat.diffuse_color = color
    mat.use_nodes = True
    mat.blend_method = "BLEND"

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()

    # Create necessary nodes
    transparent = nodes.new(type="ShaderNodeBsdfTransparent")
    emission = nodes.new(type="ShaderNodeEmission")
    mix_shader = nodes.new(type="ShaderNodeMixShader")
    output = nodes.new(type="ShaderNodeOutputMaterial")

    attr_node = nodes.new("ShaderNodeAttribute")
    attr_node.attribute_name = "opacity"
    attr_node.attribute_type = "OBJECT"

    # Set node positions
    attr_node.location = (-300, 300)
    transparent.location = (-300, 100)

    emission.location = (-300, 0)
    mix_shader.location = (0, 100)
    output.location = (300, 100)

    # Set Emission color
    emission.inputs[0].default_value = color  # Use the provided color
    emission.inputs[1].default_value = 1.0  # Emission strength

    # Link nodes
    links.new(transparent.outputs[0], mix_shader.inputs[1])
    links.new(emission.outputs[0], mix_shader.inputs[2])
    links.new(mix_shader.outputs[0], output.inputs[0])
    links.new(
        attr_node.outputs["Fac"], mix_shader.inputs[0]
    )  # Use object opacity attribute

    return mat


def deduplicate_materials(collection: bpy.types.Collection) -> None:
    """
    Deduplicate materials in a collection by reusing identical materials and giving them descriptive names.

    Args:
        collection: The collection containing objects whose materials need deduplication
    """

    # # Clean up any remaining unused materials that might have been created before
    # for _ in range(3):  # Run multiple times to ensure all orphaned data is removed
    #     bpy.ops.outliner.orphans_purge(do_recursive=True) #TODO : not very tested, and might delete some materials unintended

    materials_dict = {}

    for obj in collection.objects:
        if not obj.data.materials:
            continue

        current_mat = obj.data.materials[0]
        mat_key = tuple(current_mat.diffuse_color)

        if mat_key in materials_dict:
            obj.data.materials.clear()
            obj.data.materials.append(materials_dict[mat_key])
        else:
            rgb = current_mat.diffuse_color[:3]
            hex_color = "".join(f"{int(c*255):02x}" for c in rgb)
            mat_name = f"Mat{len(materials_dict)}_#{hex_color}"

            # Check if material already exists in Blender
            existing_mat = bpy.data.materials.get(mat_name)
            if existing_mat:
                new_mat = existing_mat
            else:
                new_mat = create_material(current_mat.diffuse_color, mat_name)

            materials_dict[mat_key] = new_mat

            obj.data.materials.clear()
            obj.data.materials.append(new_mat)

            if current_mat.users == 0:
                bpy.data.materials.remove(current_mat)

    # Clean up any remaining unused materials
    # for _ in range(3):  # Run multiple times to ensure all orphaned data is removed
    with contextlib.redirect_stdout(None):

        bpy.ops.outliner.orphans_purge(
            do_recursive=True
        )  # TODO : not very tested, and might delete some materials unintended


# Helper functions for object manipulation
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

    # Clean up any orphaned data after conversion
    # bpy.ops.outliner.orphans_purge(do_recursive=True) #TODO : not very tested, and might delete some materials unintended

def _convert_to_unfilled_paths(collection: bpy.types.Collection) -> None:
    
    """Helper function to convert curves to unfilled paths."""
    for obj in collection.objects:
        if obj.type != "CURVE":
            continue
        obj.data.fill_mode = "NONE"
        print(obj.data.fill_mode)


def _grease_pencil_material_key(material: bpy.types.Material) -> tuple:
    """Return the visible settings that identify a generated GP material."""
    style = material.grease_pencil
    return (
        style.mode,
        style.stroke_style,
        tuple(style.color),
        style.fill_style,
        tuple(style.fill_color),
        style.use_stroke_holdout,
        style.use_fill_holdout,
    )


def _deduplicate_grease_pencil_materials(
    collection: bpy.types.Collection,
) -> None:
    """Share identical native Grease Pencil materials in a collection."""
    materials_by_key = {}
    replaced_materials = set()

    for obj in collection.objects:
        if obj.type != "GREASEPENCIL":
            continue

        for index, material in enumerate(obj.data.materials):
            if material is None or material.grease_pencil is None:
                continue

            key = _grease_pencil_material_key(material)
            shared_material = materials_by_key.get(key)
            if shared_material is None:
                fill_color = material.grease_pencil.fill_color
                hex_color = "".join(
                    f"{int(max(0.0, min(1.0, component)) * 255):02x}"
                    for component in fill_color[:3]
                )
                material.name = f"GPMat{len(materials_by_key)}_#{hex_color}"
                materials_by_key[key] = material
                continue

            obj.data.materials[index] = shared_material
            replaced_materials.add(material)

    for material in replaced_materials:
        if material.users == 0:
            bpy.data.materials.remove(material)


def _convert_to_grease_pencil(
    collection: bpy.types.Collection,
    stroke_radius: float = DEFAULT_GREASE_PENCIL_STROKE_RADIUS,
) -> None:
    """Convert imported SVG Curves to native Blender 5.2 Grease Pencil data.

    Blender 5.2's converter writes the per-curve ``fill_id`` and
    ``hide_stroke`` attributes used by the current Grease Pencil fill system.
    A shared fill id keeps the outer and inner contours of glyphs together, so
    holes in characters such as ``O``, ``a``, ``0``, and ``8`` render properly.
    """
    if bpy.app.version < (5, 2, 0):
        raise RuntimeError("Grease Pencil import requires Blender 5.2 or newer")
    if stroke_radius < 0.0:
        raise ValueError("Grease Pencil stroke radius must be non-negative")

    curve_objects = [obj for obj in collection.objects if obj.type == "CURVE"]
    if not curve_objects:
        return

    source_curve_data = []
    source_materials = set()
    for obj in curve_objects:
        if obj.data not in source_curve_data:
            source_curve_data.append(obj.data)
        source_materials.update(
            material for material in obj.data.materials if material is not None
        )

    # object.convert acts on every selected editable object. Override its
    # selection context with exactly one imported Curve so pre-existing objects
    # are never included in the conversion.
    converted_objects = []
    conversion_curve_data = []
    for source_obj in curve_objects:
        original_name = source_obj.name
        objects_before_conversion = set(bpy.data.objects)
        curves_before_conversion = set(bpy.data.curves)
        with bpy.context.temp_override(
            object=source_obj,
            active_object=source_obj,
            selected_objects=[source_obj],
            selected_editable_objects=[source_obj],
        ):
            result = bpy.ops.object.convert(
                target="GREASEPENCIL",
                keep_original=True,
            )
        new_gp_objects = [
            obj
            for obj in bpy.data.objects
            if obj not in objects_before_conversion and obj.type == "GREASEPENCIL"
        ]
        conversion_curve_data.extend(
            curve
            for curve in bpy.data.curves
            if curve not in curves_before_conversion
            and curve not in conversion_curve_data
        )
        gp_obj = new_gp_objects[0] if len(new_gp_objects) == 1 else None
        if (
            result != {"FINISHED"}
            or gp_obj is None
            or gp_obj is source_obj
            or gp_obj.type != "GREASEPENCIL"
        ):
            raise RuntimeError(f"Failed to convert {original_name} to Grease Pencil")

        gp_obj.name = f"GP_{original_name}"
        gp_obj.data.name = f"GP_{original_name}DataBlock"

        # The conversion operator can leave the generated layer inactive.
        # Activating it makes the result immediately editable in Draw/Edit mode.
        if gp_obj.data.layers:
            gp_obj.data.layers.active = gp_obj.data.layers[0]

        converted_objects.append(gp_obj)
        bpy.data.objects.remove(source_obj, do_unlink=True)

    # object.convert leaves the source Curve datablocks behind for undo. They
    # are no longer referenced by Curve objects after a successful conversion.
    for curve_data in source_curve_data + conversion_curve_data:
        is_still_used = any(
            obj.type == "CURVE" and obj.data == curve_data for obj in bpy.data.objects
        )
        if not is_still_used:
            bpy.data.curves.remove(curve_data)

    for material in source_materials:
        if material.users == 0:
            bpy.data.materials.remove(material)

    # A native Grease Pencil material carries separate stroke and fill colors.
    # Keep the imported Typst color as the fill and use the black outline from
    # the previous FONT_FILL workflow.
    for obj in converted_objects:
        for material in obj.data.materials:
            if material is not None and material.grease_pencil is not None:
                material.grease_pencil.color = (0.0, 0.0, 0.0, 1.0)

    _deduplicate_grease_pencil_materials(collection)

    for obj in converted_objects:
        add_grease_pencil_stroke_radius_modifier(obj, stroke_radius)

    for obj in converted_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = converted_objects[0]


def add_indices_to_collection(imported_collection):
    """
    Add index labels to objects in a collection.
    Example:
    ```python
    content = "$ limits(integral)_a^b f(x) dif x $"
    c = typst_express(content, origin_to_char=True, name="Integral")
    indices_collection = add_indices_to_collection(c)
    ```

    Args:
        imported_collection: The collection containing objects to be indexed.

    Returns:
        The indices collection if created, otherwise None.
    """
    # Create a new collection for indices if there are multiple objects
    if len(imported_collection.objects) > 1:
        indices_collection = bpy.data.collections.new(
            f"{imported_collection.name}_Indice^s"
        )
        # Link the indices collection as a child of the imported_collection instead of scene collection
        imported_collection.children.link(indices_collection)

        for i, obj in enumerate(imported_collection.objects):
            # Create text object at the same location as the curve/mesh
            bpy.ops.object.text_add(location=(0, 0, 0))
            text_obj = bpy.context.active_object
            text_obj.data.body = str(i)
            text_obj.name = f"Index_{i}"
            bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")
            text_obj.scale = (0.15, 0.15, 0.15)

            # Make the text smaller

            # Set text color to blue
            if "Index_Material" not in bpy.data.materials:
                mat = bpy.data.materials.new("Index_Material")
                mat.diffuse_color = (0.0, 0.0, 1.0, 1.0)  # Blue color
            else:
                mat = bpy.data.materials["Index_Material"]

            if text_obj.data.materials:
                text_obj.data.materials[0] = mat
            else:
                text_obj.data.materials.append(mat)

            # Set text position to obj.location with slight z offset
            text_obj.location = (
                obj.location[0],
                obj.location[1],
                obj.location[2] + 0.009,
            )

            # Create background circle for the text
            bpy.ops.mesh.primitive_circle_add(
                vertices=32,
                radius=0.07,
                fill_type="NGON",
                location=(obj.location[0], obj.location[1], obj.location[2] + 0.005),
            )
            circle_obj = bpy.context.active_object
            circle_obj.name = f"Index_Bg_{i}"

            # Create white material for background with transparency
            if "Index_Bg_Material" not in bpy.data.materials:
                bg_mat = bpy.data.materials.new("Index_Bg_Material")
                bg_mat.diffuse_color = (
                    1.0,
                    1.0,
                    1.0,
                    0.2,
                )  # White with some transparency

                # Set up material for transparency
                bg_mat.use_nodes = True
                nodes = bg_mat.node_tree.nodes
                links = bg_mat.node_tree.links

                # Clear existing nodes
                for node in nodes:
                    nodes.remove(node)

                # Create necessary nodes
                output_node = nodes.new(type="ShaderNodeOutputMaterial")
                output_node.location = (400, 0)

                principled_node = nodes.new(type="ShaderNodeBsdfPrincipled")
                principled_node.location = (0, 0)
                principled_node.inputs["Base Color"].default_value = (
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                )
                principled_node.inputs["Alpha"].default_value = 0.2

                links.new(
                    principled_node.outputs["BSDF"], output_node.inputs["Surface"]
                )

                # Enable transparency settings for Eevee
                bg_mat.blend_method = "BLEND"
                bg_mat.use_backface_culling = False
            else:
                bg_mat = bpy.data.materials["Index_Bg_Material"]

            if circle_obj.data.materials:
                circle_obj.data.materials[0] = bg_mat
            else:
                circle_obj.data.materials.append(bg_mat)

            # Move from scene collection to indices collection
            bpy.context.scene.collection.objects.unlink(text_obj)
            indices_collection.objects.link(text_obj)

            bpy.context.scene.collection.objects.unlink(circle_obj)
            indices_collection.objects.link(circle_obj)

        return indices_collection

    return None


# Main conversion functions
def typst_to_blender_curves(
    typst_file: Path,
    scale_factor: float = 100.0,
    origin_to_char: bool = False,
    join_curves: bool = False,
    convert_to_mesh: bool = False,
    convert_to_unfilled_path: bool = False,
    position: Optional[Tuple[float, float, float]] = None,
    show_indices: bool = False,
    *,
    use_grease_pencil: bool = False,
    grease_pencil_stroke_radius: float = DEFAULT_GREASE_PENCIL_STROKE_RADIUS,
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
        convert_to_unfilled_path (bool, optional): If True, convert curves to unfilled paths. Defaults to False.
        position (Optional[Tuple[float, float, float]], optional): Position (x,y,z) to place the content. Defaults to None.
        show_indices (bool, optional): If True, add blue text indices with background circles to each object. Defaults to False.
        use_grease_pencil (bool, optional): If True, create native Blender 5.2 Grease Pencil objects. This takes precedence over mesh and unfilled-curve conversion. Defaults to False.
        grease_pencil_stroke_radius (float, optional): Initial value for the editable Stroke Radius Geometry Nodes input. Defaults to 0.01.

    Returns:
        bpy.types.Collection: The collection of imported Blender objects.
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

    # Also store on the scene so the Export panel can always access the latest SVG
    bpy.context.scene.typst_last_processed_svg = processed_svg

    # Setup objects and materials
    for obj in imported_collection.objects:
        # Rename curve objects from "Curve" to "n"
        if obj.name.startswith("Curve"):
            obj.name = "n" + obj.name[5:]
        setup_object(obj, scale_factor)

    deduplicate_materials(imported_collection)

    if join_curves and len(imported_collection.objects) > 1:
        _join_curves(imported_collection, file_name_without_ext)

    if origin_to_char:
        _set_origins_to_geometry(imported_collection)

    if use_grease_pencil:
        _convert_to_grease_pencil(
            imported_collection,
            stroke_radius=grease_pencil_stroke_radius,
        )
    elif convert_to_mesh:
        _convert_to_meshes(imported_collection)
    elif convert_to_unfilled_path:
        _convert_to_unfilled_paths(imported_collection)

    # Position the collection if coordinates are provided
    if position is not None:
        for obj in imported_collection.objects:
            # Add position as an offset to current location
            obj.location = (
                obj.location[0] + position[0],
                obj.location[1] + position[1],
                obj.location[2] + position[2],
            )

    # Add index labels if requested
    if show_indices:
        add_indices_to_collection(imported_collection)

    # Final cleanup of any remaining unused data
    # bpy.ops.outliner.orphans_purge(do_recursive=True)

    return imported_collection


def typst_express(
    content: str,
    name: str = "typst_expr",
    header: Optional[str] = None,
    scale_factor: float = 100.0,
    origin_to_char: bool = False,
    join_curves: bool = False,
    convert_to_mesh: bool = True,
    convert_to_unfilled_path: bool = False,
    position: Optional[Tuple[float, float, float]] = None,
    show_indices: bool = False,
    *,
    use_grease_pencil: bool = False,
    grease_pencil_stroke_radius: float = DEFAULT_GREASE_PENCIL_STROKE_RADIUS,
) -> bpy.types.Collection:
    """
    Create Blender objects from Typst content.

    Args:
        content (str): The main Typst content/body to be rendered
        name (str, optional): Name for the generated collection. Defaults to "typst_expr".
        header (Optional[str], optional): Typst header content with settings. If None,
                                        uses default settings for auto-sizing and text size.
        scale_factor (float, optional): Scale factor for the imported curves. Defaults to 100.0.
        origin_to_char (bool, optional): If True, set the origin of each object to its geometry. Defaults to False.
        join_curves (bool, optional): If True, join all curves into a single object. Defaults to False.
        convert_to_mesh (bool, optional): If True, convert curves to meshes. Defaults to True.
        convert_to_unfilled_path (bool, optional): If True, convert curves to unfilled paths. Defaults to False.
        position (Optional[Tuple[float, float, float]], optional): Position (x,y,z) to place the content. Defaults to None.
        show_indices (bool, optional): If True, add blue text indices with background circles to each object. Defaults to False.
        use_grease_pencil (bool, optional): If True, create native Blender 5.2 Grease Pencil objects. This takes precedence over convert_to_mesh. Defaults to False.
        grease_pencil_stroke_radius (float, optional): Initial value for the editable Stroke Radius Geometry Nodes input. Defaults to 0.01.

    Returns:
        bpy.types.Collection: The collection of imported Blender objects.
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
        typst_file=temp_file,
        scale_factor=scale_factor,
        origin_to_char=origin_to_char,
        join_curves=join_curves,
        convert_to_mesh=convert_to_mesh,
        convert_to_unfilled_path=convert_to_unfilled_path,
        use_grease_pencil=use_grease_pencil,
        position=position,
        show_indices=show_indices,
        grease_pencil_stroke_radius=grease_pencil_stroke_radius,
    )
    collection.name = name

    return collection
