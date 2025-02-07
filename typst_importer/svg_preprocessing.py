from lxml import etree
import copy
import math
import sys
import xml.etree.ElementTree as ET
from svg.path import parse_path


def flatten_svg(svg_content):
    """
    Replaces all <use xlink:href="#..."> references with the actual symbol contents,
    preserving transforms and styles so the final visual layout is unchanged.
    """
    NS_SVG = "http://www.w3.org/2000/svg"
    NS_XLINK = "http://www.w3.org/1999/xlink"
    ns = {"svg": NS_SVG, "xlink": NS_XLINK}

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


# SVG namespace – we use this when creating new elements.
SVG_NS = "http://www.w3.org/2000/svg"

# Register the namespace so that the output does not include prefixes.
ET.register_namespace("", SVG_NS)


def find_parent(root, child):
    """Helper function: given the root and a child element, find the child’s parent."""
    for parent in root.iter():
        if child in list(parent):
            return parent
    return None


def get_derivative(path_obj, t, dt=1e-6):
    """
    Compute the derivative of the path at parameter t using a finite difference.
    t is clamped between 0 and 1.
    """
    t0 = max(0, t - dt)
    t1 = min(1, t + dt)
    pt0 = path_obj.point(t0)
    pt1 = path_obj.point(t1)
    # Avoid division by zero.
    if t1 - t0 == 0:
        return complex(0, 0)
    return (pt1 - pt0) / (t1 - t0)


def stroke_to_path(d_attr, stroke_width, num_samples=1000):
    """
    Given a path data string d_attr and a stroke width,
    compute an outline that represents the painted stroke.

    We sample the original path (using svg.path.parse_path) at many points.
    At each sample point we compute the tangent (via a finite difference derivative),
    then a normal vector. We then offset the point by +offset (left side) and -offset (right side).
    Finally, we build a closed polygon that is the left offset (in order)
    and then the right offset (in reverse order).

    Note: This approximation works for any direction (and for curves) if enough
    sample points are used.
    """
    path_obj = parse_path(d_attr)
    offset = stroke_width / 2.0

    left_points = []
    right_points = []

    # Sample along the entire path from t=0 to t=1.
    for i in range(num_samples + 1):
        t = i / num_samples
        pt = path_obj.point(t)
        # Compute the derivative using our finite difference helper.
        dpt = get_derivative(path_obj, t)
        dx, dy = dpt.real, dpt.imag
        length = math.hypot(dx, dy)
        if length == 0:
            # If zero derivative (e.g. at a cusp) use the previous normal if available.
            if left_points:
                # This is a crude fallback.
                normal = (
                    (left_points[-1][0] - pt.real) / offset,
                    (left_points[-1][1] - pt.imag) / offset,
                )
            else:
                normal = (0, 0)
        else:
            # Normal is (-dy, dx) normalized.
            nx, ny = -dy / length, dx / length
            normal = (nx, ny)
        # Compute the offset points.
        left_pt = (pt.real + normal[0] * offset, pt.imag + normal[1] * offset)
        right_pt = (pt.real - normal[0] * offset, pt.imag - normal[1] * offset)
        left_points.append(left_pt)
        right_points.append(right_pt)

    # Build a closed polygon: traverse left_points, then the reversed right_points.
    d_parts = []
    d_parts.append("M {} {}".format(*left_points[0]))
    for pt in left_points[1:]:
        d_parts.append("L {} {}".format(*pt))
    for pt in reversed(right_points):
        d_parts.append("L {} {}".format(*pt))
    d_parts.append("Z")  # close path
    return " ".join(d_parts)


def stroke_to_filled_path(svg_content):
    """
    Parse the SVG content (as a string), find any <path> that has a stroke,
    convert its stroke to a filled outline path, and return the modified SVG string.
    """
    # Parse the SVG.
    root = ET.fromstring(svg_content)

    # Find SVG path elements (in the SVG namespace).
    path_elems = root.findall(".//{" + SVG_NS + "}path")
    for path_elem in path_elems:
        attrib = path_elem.attrib
        # Look for elements that have both a stroke and a stroke-width.
        if "stroke" in attrib and "stroke-width" in attrib:
            d_attr = attrib.get("d")
            try:
                stroke_width = float(attrib.get("stroke-width"))
            except ValueError:
                continue  # skip if stroke-width is not a number

            # Compute the new path data that outlines the stroke.
            new_d = stroke_to_path(d_attr, stroke_width)

            # Create a new path element (in the SVG namespace).
            new_path = ET.Element("{" + SVG_NS + "}path")
            new_path.set("d", new_d)
            # Use the original stroke color as the fill.
            new_path.set("fill", attrib.get("stroke"))
            new_path.set("fill-rule", "nonzero")

            # Optionally, copy any transform or other relevant attributes.
            if "transform" in attrib:
                new_path.set("transform", attrib.get("transform"))

            # Replace the old element with the new one.
            parent = find_parent(root, path_elem)
            if parent is not None:
                children = list(parent)
                for i, child in enumerate(children):
                    if child is path_elem:
                        parent.remove(path_elem)
                        parent.insert(i, new_path)
                        break
    # Return the modified SVG as a string.
    return ET.tostring(root, encoding="unicode")


def preprocess_svg(svg_content):
    simplified_svg = flatten_svg(svg_content)
    processed_svg = stroke_to_filled_path(simplified_svg)
    return processed_svg
