from lxml import etree
import copy
import math
import re
from svg.path import parse_path

# SVG namespace used throughout.
SVG_NS = "http://www.w3.org/2000/svg"
NS_MAP = {"svg": SVG_NS, "xlink": "http://www.w3.org/1999/xlink"}
_FLOAT_RE = re.compile(r"[+-]?\d*\.?\d+(?:[eE][+-]?\d+)?")
_LENGTH_UNITS = {
    "": 1.0,
    "px": 1.0,
    "in": 90.0,
    "mm": 90.0 / 25.4,
    "cm": 90.0 / 2.54,
    "pt": 1.25,
    "pc": 15.0,
    "em": 1.0,
    "ex": 1.0,
}
MAX_FLATTENED_SVG_NODES = 50_000
STROKE_OUTLINE_SAMPLES = 1000
MAX_STROKE_SAMPLE_POINTS = 250_000


def _viewbox(value):
    if not value:
        return None
    values = [float(token) for token in _FLOAT_RE.findall(value)]
    return tuple(values) if len(values) == 4 else None


def _viewbox_y_end(value):
    values = _viewbox(value)
    return values[1] + values[3] if values is not None else None


def _parse_preserve_aspect_ratio(value):
    tokens = (value or "xMidYMid meet").strip().split()
    if tokens and tokens[0] == "defer":
        tokens.pop(0)
    if not tokens:
        return "xMidYMid", "meet"
    if tokens[0] == "none":
        if len(tokens) > 2 or (
            len(tokens) == 2 and tokens[1] not in {"meet", "slice"}
        ):
            return "xMidYMid", "meet"
        return "none", "meet"
    align = tokens[0]
    if not re.fullmatch(r"x(?:Min|Mid|Max)Y(?:Min|Mid|Max)", align):
        return "xMidYMid", "meet"
    if len(tokens) > 2 or (
        len(tokens) == 2 and tokens[1] not in {"meet", "slice"}
    ):
        return "xMidYMid", "meet"
    return align, tokens[1] if len(tokens) == 2 else "meet"


def _alignment_factor(align, axis):
    part = align.split("Y", 1)[0][1:] if axis == "x" else align.split("Y", 1)[1]
    return {"Min": 0.0, "Mid": 0.5, "Max": 1.0}.get(part, 0.5)


def _viewport_mapping(width, height, viewbox, preserve_aspect_ratio):
    """Map viewBox coordinates into a viewport as an affine tuple."""
    vx, vy, vw, vh = viewbox
    if width == 0 or height == 0 or vw == 0 or vh == 0:
        return None
    align, mode = _parse_preserve_aspect_ratio(preserve_aspect_ratio)
    if align == "none":
        scale_x = width / vw
        scale_y = height / vh
        return scale_x, scale_y, -vx * scale_x, -vy * scale_y
    scale = (
        max(width / vw, height / vh)
        if mode == "slice"
        else min(width / vw, height / vh)
    )
    offset_x = (width - vw * scale) * _alignment_factor(align, "x")
    offset_y = (height - vh * scale) * _alignment_factor(align, "y")
    return scale, scale, offset_x - vx * scale, offset_y - vy * scale


def _viewport_alignment_correction(width, height, viewbox_value, value):
    """Return a child transform that turns Blender's default meet into PAR."""
    viewbox = _viewbox(viewbox_value)
    if viewbox is None:
        return None
    vx, vy, vw, vh = viewbox
    if width == 0 or height == 0 or vw == 0 or vh == 0:
        return None
    default_scale = min(width / vw, height / vh)
    default = (
        default_scale,
        default_scale,
        (width - vw * default_scale) / 2.0 - vx,
        (height - vh * default_scale) / 2.0 - vy,
    )
    desired = _viewport_mapping(width, height, viewbox, value)
    if desired is None:
        return None
    default_x, default_y, default_tx, default_ty = default
    desired_x, desired_y, desired_tx, desired_ty = desired
    correction = (
        desired_x / default_x,
        desired_y / default_y,
        (desired_tx - default_tx) / default_x,
        (desired_ty - default_ty) / default_y,
    )
    if all(
        math.isclose(actual, expected, abs_tol=1e-12)
        for actual, expected in zip(correction, (1.0, 1.0, 0.0, 0.0))
    ):
        return None
    return correction


def _parse_length(value, reference, default):
    if value is None or value.strip().lower() == "auto":
        return default
    match = _FLOAT_RE.match(value.strip())
    if match is None:
        return default
    parsed = float(match.group(0))
    unit = value.strip()[match.end() :].strip()
    if unit == "%":
        return reference * parsed / 100.0
    return parsed * _LENGTH_UNITS.get(unit, 1.0)


def _active_viewport(element):
    """Return the nearest SVG user-coordinate viewport dimensions."""
    viewport = (0.0, 0.0)
    ancestors = list(element.iterancestors())
    ancestors.reverse()
    for ancestor in ancestors:
        if not isinstance(ancestor.tag, str):
            continue
        qname = etree.QName(ancestor.tag)
        if qname.namespace not in (None, SVG_NS) or qname.localname != "svg":
            continue
        viewbox = _viewbox(ancestor.get("viewBox"))
        if viewbox is not None:
            viewport = (viewbox[2], viewbox[3])
        else:
            viewport = (
                _parse_length(
                    ancestor.get("width"), viewport[0], viewport[0]
                ),
                _parse_length(
                    ancestor.get("height"), viewport[1], viewport[1]
                ),
            )
    return viewport


def _number(value):
    return format(value, ".15g")


def _ensure_unicode(xml_string):
    """
    Ensures the input XML string is a Unicode string without an XML encoding declaration.
    If the input is bytes, decodes as UTF-8.
    If the input is str, strips any XML encoding declaration.
    """
    if isinstance(xml_string, bytes):
        xml_string = xml_string.decode("utf-8")
    # Remove XML encoding declaration if present
    import re
    xml_string = re.sub(r'<\?xml[^>]*encoding=[\'"].*?[\'"][^>]*\?>', '', xml_string, flags=re.IGNORECASE)
    return xml_string


def parse_svg_string(svg_content):
    """
    Parses SVG content into an lxml root element, handling XML declarations,
    doctypes and other preamble if present.
    """
    svg_content = _ensure_unicode(svg_content)
    try:
        # First try parsing as a direct XML fragment
        return etree.fromstring(svg_content)
    except etree.XMLSyntaxError:
        try:
            # Try parsing as an XML document with potential XML declaration
            parser = etree.XMLParser(remove_blank_text=True)
            return etree.fromstring(svg_content, parser)
        except:
            # If still failing, try to handle SVG with doctype or other preamble
            # by extracting just the SVG element
            import re
            svg_match = re.search(r'<svg[^>]*>.*</svg>', svg_content, re.DOTALL)
            if svg_match:
                parser = etree.XMLParser(remove_blank_text=True)
                return etree.fromstring(svg_match.group(0), parser)
            else:
                raise


def flatten_svg(svg_content):
    """
    Replaces all <use xlink:href="#..."> references with the actual symbol contents,
    preserving transforms and styles so the final visual layout is unchanged.
    """
    tree = parse_svg_string(svg_content)
    node_count = sum(1 for _ in tree.iter())
    if node_count > MAX_FLATTENED_SVG_NODES:
        raise ValueError("SVG exceeds the preprocessing expansion limit")

    # Blender's SVG importer does not descend into hyperlink containers.
    # Normalize them to groups so their visual children (including image
    # paint-order markers) remain part of the imported rendering tree.
    for link in tree.xpath("//svg:a", namespaces=NS_MAP):
        link.tag = f"{{{SVG_NS}}}g"
        link.attrib.pop("href", None)
        link.attrib.pop(f"{{{NS_MAP['xlink']}}}href", None)

    # Collect every element that can be referenced by ID; <use> may point at
    # any element with an id, not only <symbol> inside <defs>.
    elements_by_id = {}
    for el in tree.xpath("//*[@id]"):
        elements_by_id[el.get("id")] = el

    # Replace each <use> element with a group containing a clone of its
    # referenced element. Repeat to resolve <use> references nested inside
    # cloned content (bounded to guard against reference cycles).
    for _ in range(10):
        use_elements = tree.xpath(
            "//svg:use[not(ancestor::svg:defs)]", namespaces=NS_MAP
        )
        if not use_elements:
            break
        for use_el in use_elements:
            # SVG 1.1 uses xlink:href, SVG 2 uses plain href.
            # SVG 2 plain href takes precedence when both forms are present.
            href = use_el.get("href")
            if href is None:
                href = use_el.get(f"{{{NS_MAP['xlink']}}}href")
            if not (href and href.startswith("#")):
                continue
            target = elements_by_id.get(href[1:])
            if target is None:
                continue

            # Check before deepcopying: recursive or heavily branching <use>
            # graphs can otherwise grow exponentially before image resource
            # limits get a chance to run.  Eight is the maximum synthetic
            # wrapper overhead used below.
            target_node_count = sum(1 for _ in target.iter())
            if (
                node_count - 1 + target_node_count + 8
                > MAX_FLATTENED_SVG_NODES
            ):
                raise ValueError("SVG exceeds the preprocessing expansion limit")

            # Keep the use transform and presentation properties on an outer
            # group.  A nested SVG carries x/y as real length properties, so
            # valid percentages and units remain viewport-aware instead of
            # being forced through float() or an invalid transform length.
            new_g = etree.Element(f"{{{SVG_NS}}}g")
            transform = use_el.get("transform", "")
            if transform:
                new_g.set("transform", transform)

            # Copy over any additional attributes (such as fill, etc.).
            for attr_name, attr_value in use_el.items():
                if attr_name not in (
                    "x",
                    "y",
                    "width",
                    "height",
                    "transform",
                    "href",
                    f"{{{NS_MAP['xlink']}}}href",
                ):
                    new_g.set(attr_name, attr_value)

            # Keep the referenced element's transform outside its node/viewport
            # matrix, matching Blender's native use instancing order.
            local_name = etree.QName(target).localname
            if local_name in ("symbol", "svg"):
                parent_width, parent_height = _active_viewport(use_el)
                use_x = _parse_length(use_el.get("x"), parent_width, 0.0)
                use_y = _parse_length(use_el.get("y"), parent_height, 0.0)

                width_value = use_el.get("width")
                if width_value is None or width_value.strip().lower() == "auto":
                    width_value = target.get("width")
                height_value = use_el.get("height")
                if height_value is None or height_value.strip().lower() == "auto":
                    height_value = target.get("height")
                width = _parse_length(
                    width_value, parent_width, parent_width
                )
                height = _parse_length(
                    height_value, parent_height, parent_height
                )

                placement = etree.Element(f"{{{SVG_NS}}}g")
                if use_x != 0 or use_y != 0:
                    placement.set(
                        "transform",
                        f"translate({_number(use_x)},{_number(use_y)})",
                    )
                target_group = etree.Element(f"{{{SVG_NS}}}g")
                for attr_name, attr_value in target.items():
                    if attr_name not in {
                        "id",
                        "x",
                        "y",
                        "width",
                        "height",
                        "viewBox",
                        "preserveAspectRatio",
                    }:
                        target_group.set(attr_name, attr_value)

                # The referenced element's x/y percentages stay in the
                # coordinate system where the instance is placed; changing
                # the instance width/height must not change their basis.
                target_x = _parse_length(target.get("x"), parent_width, 0.0)
                target_y = _parse_length(target.get("y"), parent_height, 0.0)
                target_position = etree.Element(f"{{{SVG_NS}}}g")
                if target_x != 0 or target_y != 0:
                    target_position.set(
                        "transform",
                        f"translate({_number(target_x)},{_number(target_y)})",
                    )

                viewport_compensation = etree.Element(f"{{{SVG_NS}}}g")
                scale_x = parent_width / width if width != 0 else 1.0
                scale_y = parent_height / height if height != 0 else 1.0
                if scale_x != 1.0 or scale_y != 1.0:
                    viewport_compensation.set(
                        "transform",
                        f"scale({_number(scale_x)},{_number(scale_y)})",
                    )

                target_viewport = etree.Element(f"{{{SVG_NS}}}svg")
                target_viewport.set("width", _number(width))
                target_viewport.set("height", _number(height))
                viewbox_value = target.get("viewBox")
                if viewbox_value is not None:
                    target_viewport.set("viewBox", viewbox_value)

                content_parent = target_viewport
                if local_name in ("symbol", "svg"):
                    # Blender adds a document-origin shift to nested SVG nodes
                    # that is not part of native <use> instancing.  Cancel it
                    # for both cloned symbols and cloned SVG viewports; authored
                    # nested SVG elements elsewhere in the document are left
                    # untouched.
                    y_end = _viewbox_y_end(target.get("viewBox"))
                    if y_end is not None:
                        compensation = etree.Element(f"{{{SVG_NS}}}g")
                        compensation.set("transform", f"translate(0,{y_end})")
                        target_viewport.append(compensation)
                        content_parent = compensation
                alignment_correction = _viewport_alignment_correction(
                    width,
                    height,
                    viewbox_value,
                    target.get("preserveAspectRatio"),
                )
                if alignment_correction is not None:
                    scale_x, scale_y, translate_x, translate_y = (
                        alignment_correction
                    )
                    correction = etree.Element(f"{{{SVG_NS}}}g")
                    correction.set(
                        "transform",
                        "matrix("
                        f"{_number(scale_x)} 0 0 {_number(scale_y)} "
                        f"{_number(translate_x)} {_number(translate_y)})",
                    )
                    content_parent.append(correction)
                    content_parent = correction
                for child in target:
                    content_parent.append(copy.deepcopy(child))
                viewport_compensation.append(target_viewport)
                target_position.append(viewport_compensation)
                target_group.append(target_position)
                placement.append(target_group)
                new_g.append(placement)
            else:
                use_viewport = etree.Element(f"{{{SVG_NS}}}svg")
                use_viewport.set("x", use_el.get("x", "0"))
                use_viewport.set("y", use_el.get("y", "0"))
                clone = copy.deepcopy(target)
                # Drop the id so the flattened output has no duplicate ids.
                clone.attrib.pop("id", None)
                use_viewport.append(clone)
                new_g.append(use_viewport)

            # Replace the <use> element with the new group.
            parent = use_el.getparent()
            if parent is not None:
                parent.replace(use_el, new_g)
                node_count += sum(1 for _ in new_g.iter()) - 1

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


def stroke_to_path(d_attr, stroke_width, num_samples=STROKE_OUTLINE_SAMPLES):
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
    root = parse_svg_string(svg_content)

    # Find all <path> elements (using XPath with our namespace map), then
    # preflight the aggregate sampling work before constructing any large
    # outline strings.  A branching <use> graph can clone many stroked paths
    # while still remaining below the general XML node limit.
    path_elems = root.xpath(".//svg:path", namespaces=NS_MAP)
    candidates = []
    for path_elem in path_elems:
        attrib = path_elem.attrib
        stroke = attrib.get("stroke")
        if stroke is None or stroke.strip().lower() == "none":
            continue
        if "stroke-width" not in attrib:
            continue
        d_attr = attrib.get("d")
        if not d_attr:
            continue
        try:
            stroke_width = float(attrib.get("stroke-width"))
        except ValueError:
            continue
        if stroke_width <= 0:
            continue

        candidates.append((path_elem, d_attr, stroke_width, stroke))

    if len(candidates) * (STROKE_OUTLINE_SAMPLES + 1) > MAX_STROKE_SAMPLE_POINTS:
        raise ValueError("SVG exceeds the stroke conversion work limit")

    for path_elem, d_attr, stroke_width, stroke in candidates:
        attrib = path_elem.attrib
        # Convert the stroke to a filled outline.
        new_d = stroke_to_path(
            d_attr, stroke_width, num_samples=STROKE_OUTLINE_SAMPLES
        )

        # Create a new <path> element with the computed outline.
        new_path = etree.Element(f"{{{SVG_NS}}}path")
        new_path.set("d", new_d)
        new_path.set("fill", stroke)
        new_path.set("fill-rule", "nonzero")
        if "transform" in attrib:
            new_path.set("transform", attrib.get("transform"))

        parent = path_elem.getparent()
        if parent is None:
            continue

        fill = attrib.get("fill")
        if fill is not None and fill.strip().lower() == "none":
            # Stroke-only path: the outline fully replaces it.
            parent.replace(path_elem, new_path)
        else:
            # The path also has a visible fill (explicit, or the SVG default
            # black when no fill attribute is set): keep the filled path and
            # paint the stroke outline on top of it.
            for stroke_attr in (
                "stroke",
                "stroke-width",
                "stroke-linecap",
                "stroke-linejoin",
                "stroke-opacity",
                "stroke-dasharray",
                "stroke-dashoffset",
                "stroke-miterlimit",
            ):
                attrib.pop(stroke_attr, None)
            parent.insert(parent.index(path_elem) + 1, new_path)

    return etree.tostring(root, encoding="unicode", pretty_print=True)


# def convert_text_to_paths(svg_content):
#     """
#     Converts all text elements in the SVG to path elements.
#     Uses the text_to_path module to convert text to actual glyph outlines.
#     """
#     from text_to_path import convert_text_to_paths_in_svg
#     return convert_text_to_paths_in_svg(svg_content)


def preprocess_svg(svg_content):
    """
    Performs a three-step preprocessing on the SVG content:
      1. Flattens the SVG by inlining symbols (via flatten_svg).
      2. Converts text elements to path elements (via convert_text_to_paths).
      3. Converts stroked paths into filled outline paths (via stroke_to_filled_path).

    Returns the fully processed SVG content as a string.
    """
    svg_processed = flatten_svg(svg_content)
    # svg_processed = convert_text_to_paths(svg_processed) # not yet ready for use
    svg_processed = stroke_to_filled_path(svg_processed)
    return svg_processed
