from lxml import etree
import copy
import math
from svg.path import parse_path

# SVG namespace used throughout.
SVG_NS = "http://www.w3.org/2000/svg"
NS_MAP = {"svg": SVG_NS, "xlink": "http://www.w3.org/1999/xlink"}


def flatten_svg(svg_content):
    """
    Replaces all <use xlink:href="#..."> references with the actual symbol contents,
    preserving transforms and styles so the final visual layout is unchanged.
    """
    tree = etree.fromstring(svg_content)

    # Collect all <symbol> elements by ID.
    symbols = {}
    for symbol in tree.xpath("//svg:defs/svg:symbol", namespaces=NS_MAP):
        symbol_id = symbol.get("id")
        if symbol_id:
            symbols[symbol_id] = symbol

    # Replace each <use> element with a group containing a clone of its referenced symbol.
    for use_el in tree.xpath("//svg:use", namespaces=NS_MAP):
        href = use_el.get(f"{{{NS_MAP['xlink']}}}href")
        if href and href.startswith("#"):
            symbol_id = href[1:]
            symbol = symbols.get(symbol_id)
            if symbol is not None:
                # Create a new group (<g>) to hold the cloned content.
                new_g = etree.Element(f"{{{SVG_NS}}}g")

                # Incorporate any x, y, and transform attributes.
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

                # Copy over any additional attributes (such as fill, etc.).
                for attr_name, attr_value in use_el.items():
                    if attr_name not in (
                        "x",
                        "y",
                        "transform",
                        f"{{{NS_MAP['xlink']}}}href",
                    ):
                        new_g.set(attr_name, attr_value)

                # Deep-clone each child of the referenced symbol into the new group.
                for child in symbol:
                    new_g.append(copy.deepcopy(child))

                # Replace the <use> element with the new group.
                parent = use_el.getparent()
                if parent is not None:
                    parent.replace(use_el, new_g)

    # Remove the entire <defs> section (no longer needed).
    for defs in tree.xpath("//svg:defs", namespaces=NS_MAP):
        parent = defs.getparent()
        if parent is not None:
            parent.remove(defs)

    # (Optional) Clean up root <svg> attributes.
    allowed_attribs = {
        "viewBox",
        "width",
        "height",
        "xmlns",
        "version",
        "class",
        "style",
        "preserveAspectRatio",
        "baseProfile",
        f"{{{NS_MAP['xlink']}}}xmlns",
    }
    for attr in list(tree.attrib.keys()):
        if attr not in allowed_attribs:
            del tree.attrib[attr]

    return etree.tostring(tree, encoding="unicode", pretty_print=True)


def get_derivative(path_obj, t, dt=1e-6):
    """
    Compute the derivative of the path at parameter t using a finite difference.
    t is clamped between 0 and 1.
    """
    t0 = max(0, t - dt)
    t1 = min(1, t + dt)
    pt0 = path_obj.point(t0)
    pt1 = path_obj.point(t1)
    if t1 - t0 == 0:
        return complex(0, 0)
    return (pt1 - pt0) / (t1 - t0)


def stroke_to_path(d_attr, stroke_width, num_samples=1000):
    """
    Given a path data string (d_attr) and a stroke width, compute an outline
    representing the painted stroke.

    This function samples points along the path, calculates a normal at each point
    (using a finite difference derivative), and builds a closed polygon that follows
    the left side (offset positively) and the right side (offset negatively) of the path.
    """
    path_obj = parse_path(d_attr)
    offset = stroke_width / 2.0

    left_points = []
    right_points = []

    # Sample along the path.
    for i in range(num_samples + 1):
        t = i / num_samples
        pt = path_obj.point(t)
        dpt = get_derivative(path_obj, t)
        dx, dy = dpt.real, dpt.imag
        length = math.hypot(dx, dy)
        if length == 0:
            # Use previous normal as a crude fallback.
            normal = (
                (
                    (left_points[-1][0] - pt.real) / offset,
                    (left_points[-1][1] - pt.imag) / offset,
                )
                if left_points
                else (0, 0)
            )
        else:
            nx, ny = -dy / length, dx / length
            normal = (nx, ny)
        left_pt = (pt.real + normal[0] * offset, pt.imag + normal[1] * offset)
        right_pt = (pt.real - normal[0] * offset, pt.imag - normal[1] * offset)
        left_points.append(left_pt)
        right_points.append(right_pt)

    # Construct the outline path data.
    d_parts = ["M {} {}".format(*left_points[0])]
    d_parts.extend("L {} {}".format(*pt) for pt in left_points[1:])
    d_parts.extend("L {} {}".format(*pt) for pt in reversed(right_points))
    d_parts.append("Z")
    return " ".join(d_parts)


def stroke_to_filled_path(svg_content):
    """
    Parses the SVG content (as a string), finds any <path> elements that use a stroke,
    converts each stroke to a filled outline path, and returns the modified SVG as a string.
    """
    # Parse using lxml.
    root = etree.fromstring(svg_content)

    # Find all <path> elements (using XPath with our namespace map).
    path_elems = root.xpath(".//svg:path", namespaces=NS_MAP)
    for path_elem in path_elems:
        attrib = path_elem.attrib
        if "stroke" in attrib and "stroke-width" in attrib:
            d_attr = attrib.get("d")
            try:
                stroke_width = float(attrib.get("stroke-width"))
            except ValueError:
                continue

            # Convert the stroke to a filled outline.
            new_d = stroke_to_path(d_attr, stroke_width)

            # Create a new <path> element with the computed outline.
            new_path = etree.Element(f"{{{SVG_NS}}}path")
            new_path.set("d", new_d)
            new_path.set("fill", attrib.get("stroke"))
            new_path.set("fill-rule", "nonzero")
            if "transform" in attrib:
                new_path.set("transform", attrib.get("transform"))

            # Replace the old path with the new one.
            parent = path_elem.getparent()
            if parent is not None:
                parent.replace(path_elem, new_path)

    return etree.tostring(root, encoding="unicode", pretty_print=True)


def preprocess_svg(svg_content):
    """
    Performs a two-step preprocessing on the SVG content:
      1. Flattens the SVG by inlining symbols (via flatten_svg).
      2. Converts stroked paths into filled outline paths (via stroke_to_filled_path).

    Returns the fully processed SVG content as a string.
    """
    simplified_svg = flatten_svg(svg_content)
    processed_svg = stroke_to_filled_path(simplified_svg)
    return processed_svg
