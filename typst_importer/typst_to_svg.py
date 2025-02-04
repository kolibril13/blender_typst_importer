from pathlib import Path
import tempfile
import databpy as db
import bpy
from lxml import etree
import typst


def simplify_svg(step1_content):
    # Define namespaces used in the SVG.
    ns = {"svg": "http://www.w3.org/2000/svg", "xlink": "http://www.w3.org/1999/xlink"}

    # Parse the SVG.
    tree = etree.fromstring(step1_content)

    # Build a dictionary mapping symbol IDs to the symbol elements.
    symbols = {}
    for symbol in tree.xpath("//svg:defs/svg:symbol", namespaces=ns):
        symbol_id = symbol.get("id")
        symbols[symbol_id] = symbol

    # Process each <use> element.
    for use in tree.xpath("//svg:use", namespaces=ns):
        href = use.get("{http://www.w3.org/1999/xlink}href")
        if href and href.startswith("#"):
            symbol_id = href[1:]
            symbol = symbols.get(symbol_id)
            if symbol is not None:
                # For simplicity, assume the symbol contains a single <path>.
                path = symbol.find("{http://www.w3.org/2000/svg}path")
                if path is not None:
                    # Create a new <path> element.
                    new_path = etree.Element("{http://www.w3.org/2000/svg}path")
                    # Copy the "d" attribute from the symbol's <path>.
                    new_path.set("d", path.get("d"))
                    # Copy attributes from the <use> element (like fill and fill-rule).
                    for attr in ["fill", "fill-rule"]:
                        value = use.get(attr)
                        if value:
                            new_path.set(attr, value)
                    # Replace the <use> element with the new <path>.
                    parent = use.getparent()
                    parent.replace(use, new_path)

    # Remove the <defs> section since it's no longer needed.
    for defs in tree.xpath("//svg:defs", namespaces=ns):
        parent = defs.getparent()
        parent.remove(defs)

    # Optionally, remove extra attributes from the root <svg>.
    allowed_attribs = ["viewBox", "width", "height", "xmlns"]
    for attr in list(tree.attrib.keys()):
        if attr not in allowed_attribs:
            del tree.attrib[attr]

    # Convert the modified SVG tree back to a string and return it.
    step2_content = etree.tostring(tree, pretty_print=True, encoding="unicode")
    return step2_content


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


def compile_and_import_typst(typst_file: Path) -> db.BlenderObject:
    """
    Compile a .txt or .typ file to an SVG using Typst,
    then import the generated SVG into Blender.

    Args:
        typst_file (Path): The path to the .txt or .typ file.

    Returns:
        Path: The path to the generated SVG file.
    """
    file_name_without_ext = typst_file.stem

    # Create a temporary SVG file path
    temp_dir = Path(tempfile.gettempdir())
    svg_file_name = f"{file_name_without_ext}.svg"
    svg_file = temp_dir / svg_file_name
    # Compile the input file to an SVG via Typst
    typst.compile(typst_file, format="svg", output=str(svg_file))

    step1_content = svg_file.read_text()
    # print(step1_content)
    step2_content = simplify_svg(step1_content)
    # print(step2_content)
    step3_content = replace_stroke_with_path(step2_content)
    # print(step3_content)
    svg_file3 = temp_dir / "step3.svg"
    svg_file3.write_text(step3_content)
    # Import the generated SVG into Blender
    with db.ObjectTracker() as o:
        bpy.ops.import_curve.svg(filepath=str(svg_file3))
        bob = db.BlenderObject(o.latest())
    return bob
