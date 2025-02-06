from lxml import etree
import copy


def simplify_svg(svg_content):
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


def create_thick_line_path(x1, y1, x2, y2, thickness):
    """
    Create a path that represents a thick horizontal line as a rectangle.
    The line goes from (x1,y1) to (x2,y2) with given thickness.
    """
    half_thickness = thickness / 2
    path_d = (
        f"M {x1} {y1-half_thickness} "  # Start at top-left
        f"L {x2} {y2-half_thickness} "  # Line to top-right
        f"L {x2} {y2+half_thickness} "  # Line to bottom-right
        f"L {x1} {y1+half_thickness} "  # Line to bottom-left
        f"Z"
    )
    return path_d


def replace_stroke_with_path(svg_content):
    """Convert stroked paths to filled paths in the given SVG content."""
    parser = etree.XMLParser(remove_blank_text=True)
    svg_root = etree.fromstring(svg_content.strip(), parser)
    for path in svg_root.findall(".//*[@stroke-width]"):
        original_d = path.get("d")
        stroke_width = float(path.get("stroke-width"))
        parts = original_d.strip().split()
        if len(parts) >= 6 and parts[0] == "M" and parts[3] == "L":
            x1, y1 = float(parts[1]), float(parts[2])
            x2, y2 = float(parts[4]), float(parts[5])
            path.set("d", create_thick_line_path(x1, y1, x2, y2, stroke_width))
            path.set("fill", path.get("stroke", "#000000"))
            for attr in [
                "stroke",
                "stroke-width",
                "stroke-linecap",
                "stroke-linejoin",
                "stroke-miterlimit",
            ]:
                if attr in path.attrib:
                    del path.attrib[attr]
            if path.get("fill") == "none":
                path.set("fill", "#000000")
    return etree.tostring(svg_root, pretty_print=True, encoding="unicode") 