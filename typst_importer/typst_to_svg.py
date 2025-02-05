from pathlib import Path
import tempfile

import bpy
from lxml import etree
import copy
import typst


def simplify_svg(svg_content):
    """
    Replaces all <use xlink:href="#..."> references with the actual symbol contents,
    preserving transforms and styles so the final visual layout is unchanged.
    """
    # Namespaces
    NS_SVG = "http://www.w3.org/2000/svg"
    NS_XLINK = "http://www.w3.org/1999/xlink"
    ns = {"svg": NS_SVG, "xlink": NS_XLINK}

    # Parse the root SVG
    tree = etree.fromstring(svg_content)

    # Collect all <symbol> elements by ID
    symbols = {}
    for symbol in tree.xpath("//svg:defs/svg:symbol", namespaces=ns):
        symbol_id = symbol.get("id")
        if symbol_id:
            symbols[symbol_id] = symbol

    # For each <use>, replace it with the cloned children of its referenced <symbol>
    uses = tree.xpath("//svg:use", namespaces=ns)
    for use_el in uses:
        href = use_el.get(f"{{{NS_XLINK}}}href")
        if href and href.startswith("#"):
            symbol_id = href[1:]
            symbol = symbols.get(symbol_id)
            if symbol is not None:
                # Create a group <g> that will hold the symbol's cloned content
                new_g = etree.Element(f"{{{NS_SVG}}}g")

                # If <use> has x,y, or a transform, incorporate that into <g>
                x = float(use_el.get("x", "0"))
                y = float(use_el.get("y", "0"))
                transform = use_el.get("transform", "")

                transforms = []
                if x != 0 or y != 0:
                    transforms.append(f"translate({x},{y})")
                if transform:
                    transforms.append(transform)
                if transforms:
                    new_g.set("transform", " ".join(transforms))

                # Copy any other attributes (like fill) from <use> onto the group
                for attr_name, attr_value in use_el.items():
                    if attr_name not in ("x", "y", "transform", f"{{{NS_XLINK}}}href"):
                        new_g.set(attr_name, attr_value)

                # Deep-clone each child of <symbol> into this group
                for child in symbol:
                    new_g.append(copy.deepcopy(child))

                # Now replace the <use> in the tree with our new <g>
                use_parent = use_el.getparent()
                use_parent.replace(use_el, new_g)

    # Remove the entire <defs> section since we no longer need symbols
    for defs in tree.xpath("//svg:defs", namespaces=ns):
        defs_parent = defs.getparent()
        if defs_parent is not None:
            defs_parent.remove(defs)

    # (Optional) Clean up root <svg> attributes if desired
    allowed_attribs = [
        "viewBox",
        "width",
        "height",
        "xmlns",
        "version",
        "class",
        "style",
        "preserveAspectRatio",
        "baseProfile",
        f"{{{NS_XLINK}}}xmlns",
    ]
    for attr in list(tree.attrib.keys()):
        if attr not in allowed_attribs:
            del tree.attrib[attr]

    # Return the flattened SVG as text
    return etree.tostring(tree, encoding="unicode", pretty_print=True)


def create_thick_line_path(x1, y1, x2, y2, thickness):
    """
    Create a path that represents a thick horizontal line as a rectangle.
    The line goes from (x1,y1) to (x2,y2) with given thickness.
    """
    # Half thickness to extend above and below the line
    half_thickness = thickness / 2

    # Create a simple rectangle
    path_d = (
        f"M {x1} {y1-half_thickness} "  # Start at top-left
        f"L {x2} {y2-half_thickness} "  # Line to top-right
        f"L {x2} {y2+half_thickness} "  # Line to bottom-right
        f"L {x1} {y1+half_thickness} "  # Line to bottom-left
        f"Z"
    )  # Close the path

    return path_d


def replace_stroke_with_path(svg_content):
    """Convert stroked paths to filled paths in the given SVG content."""
    # Parse the SVG string
    parser = etree.XMLParser(remove_blank_text=True)
    svg_root = etree.fromstring(svg_content.strip(), parser)

    # Find all paths that have a stroke-width
    for path in svg_root.findall(".//*[@stroke-width]"):
        # Get the original path data and stroke width
        original_d = path.get("d")
        stroke_width = float(path.get("stroke-width"))

        # Parse the path data to get coordinates
        parts = original_d.strip().split()
        if len(parts) >= 6 and parts[0] == "M" and parts[3] == "L":
            x1, y1 = float(parts[1]), float(parts[2])
            x2, y2 = float(parts[4]), float(parts[5])

            # Create new path attributes
            path.set("d", create_thick_line_path(x1, y1, x2, y2, stroke_width))
            path.set("fill", path.get("stroke", "#000000"))  # Use stroke color as fill

            # Remove stroke attributes
            for attr in [
                "stroke",
                "stroke-width",
                "stroke-linecap",
                "stroke-linejoin",
                "stroke-miterlimit",
            ]:
                if attr in path.attrib:
                    del path.attrib[attr]

            # Make sure there's no 'fill' attribute set to 'none'
            if path.get("fill") == "none":
                path.set("fill", "#000000")

    return etree.tostring(svg_root, pretty_print=True, encoding="unicode")


def typst_to_blender_curves(
    typst_file: Path, scale_factor: float = 100.0, origin_to_char: bool = False
) -> bpy.types.Collection:
    """
    Compile a .txt or .typ file to an SVG using Typst,
    then import the generated SVG into Blender.

    Args:
        typst_file (Path): The path to the .txt or .typ file.
        scale_factor (float, optional): Scale factor for the imported curves. Defaults to 100.0.
        origin_to_char (bool, optional): If True, set the origin of each object to its geometry. Defaults to False.

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
    step2_content = simplify_svg(step1_content)
    step3_content = replace_stroke_with_path(step2_content)

    svg_file3 = temp_dir / "step3.svg"
    svg_file3.write_text(step3_content)
    # Import the generated SVG into Blender
    bpy.ops.import_curve.svg(filepath=str(svg_file3))

    imported_collection = bpy.context.scene.collection.children.get(svg_file3.name)
    imported_collection.name = f"Typst_{file_name_without_ext}"

    for obj in imported_collection.objects:
        obj.scale = (scale_factor, scale_factor, scale_factor)

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

    return imported_collection


def typst_express(
    content: str,
    name: str = "typst_expr",
    header: str = "",
    scale_factor: float = 100.0,
    origin_to_char: bool = False,
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
    collection = typst_to_blender_curves(temp_file, scale_factor, origin_to_char)

    # Rename the collection to the specified name
    collection.name = name

    return collection
