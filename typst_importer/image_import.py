"""Import raster images embedded in, or referenced by, an SVG document.

Image extraction runs on the fully preprocessed SVG.  Referenced definitions
have therefore already been flattened into paint order, which keeps image
placements and Blender's curve importer on the same transform path.  During
import, each image is replaced by a temporary marker curve.  The marker lets
us substitute the textured plane at the exact position in Blender's
collection order and preserve the SVG painter model.
"""

import base64
import hashlib
import math
import os
import re
import tempfile
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from lxml import etree

from .svg_preprocessing import NS_MAP, SVG_NS, parse_svg_string


XLINK_HREF = f"{{{NS_MAP['xlink']}}}href"

# Same unit table as io_curve_svg (90 dpi user units).
SVG_UNITS = {
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

# io_curve_svg maps 90 SVG user units to 1 inch (0.0254 m), Y pointing down.
BLENDER_SCALE = 1.0 / 90.0 * 0.3048 / 12.0

# A small object-space separation is needed because transparent and opaque
# coplanar surfaces still tie at much smaller offsets in Eevee.
PAINT_ORDER_Z_STEP = 0.0001

# Resource limits keep an untrusted SVG from expanding into unbounded memory.
MAX_IMAGE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 512 * 1024 * 1024
MAX_IMAGE_PLACEMENTS = 10_000
MAX_SVG_TRAVERSAL_DEPTH = 256

_FLOAT_RE = re.compile(r"[+-]?\d*\.?\d+(?:[eE][+-]?\d+)?")
_TRANSFORM_RE = re.compile(r"\s*([A-Za-z]+)\s*\((.*?)\)")
_DATA_URI_RE = re.compile(
    r"data:(?P<mime>[^;,]*)(?P<params>(?:;[^;,]*)*),(?P<data>.*)",
    re.DOTALL | re.IGNORECASE,
)
_WINDOWS_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")
_BLENDER_SUFFIX_RE = re.compile(r"^(.*)\.\d{3}$")

_MIME_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/tiff": ".tif",
    "image/avif": ".avif",
}


# --- 2D affine matrices, stored as (a, b, c, d, e, f) like SVG matrix():
#     x' = a*x + c*y + e
#     y' = b*x + d*y + f

MAT_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def mat_mul(m, n):
    """Return matrix product ``m @ n`` (``n`` is applied first)."""
    a1, b1, c1, d1, e1, f1 = m
    a2, b2, c2, d2, e2, f2 = n
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def mat_apply(m, point):
    a, b, c, d, e, f = m
    x, y = point
    return (a * x + c * y + e, b * x + d * y + f)


def mat_translate(tx, ty):
    return (1.0, 0.0, 0.0, 1.0, tx, ty)


def mat_scale(sx, sy):
    return (sx, 0.0, 0.0, sy, 0.0, 0.0)


def parse_transform(transform):
    """Parse an SVG transform list into a single affine matrix."""
    m = MAT_IDENTITY
    for match in _TRANSFORM_RE.finditer(transform):
        func = match.group(1)
        params = [float(p) for p in _FLOAT_RE.findall(match.group(2))]
        if func == "matrix" and len(params) == 6:
            t = tuple(params)
        elif func == "translate" and params:
            t = mat_translate(params[0], params[1] if len(params) > 1 else 0.0)
        elif func == "scale" and params:
            t = mat_scale(params[0], params[1] if len(params) > 1 else params[0])
        elif func == "rotate" and params:
            angle = math.radians(params[0])
            rotation = (
                math.cos(angle),
                math.sin(angle),
                -math.sin(angle),
                math.cos(angle),
                0.0,
                0.0,
            )
            if len(params) >= 3:
                cx, cy = params[1], params[2]
                t = mat_mul(
                    mat_mul(mat_translate(cx, cy), rotation),
                    mat_translate(-cx, -cy),
                )
            else:
                t = rotation
        elif func == "skewX" and params:
            t = (
                1.0,
                0.0,
                math.tan(math.radians(params[0])),
                1.0,
                0.0,
                0.0,
            )
        elif func == "skewY" and params:
            t = (
                1.0,
                math.tan(math.radians(params[0])),
                0.0,
                1.0,
                0.0,
                0.0,
            )
        else:
            continue
        m = mat_mul(m, t)
    return m


def parse_coord(coord, size=0.0):
    """Parse an SVG coordinate or length against the active viewport size."""
    coord = coord.strip()
    match = _FLOAT_RE.match(coord)
    if not match:
        return 0.0
    value = float(match.group(0))
    unit = coord[match.end() :].strip()
    if unit == "%":
        return float(size) / 100.0 * value
    return value * SVG_UNITS.get(unit, 1.0)


def _parse_image_length(value, size):
    """Return a used image length, or ``None`` for SVG 2 ``auto``."""
    if value is None or value.strip().lower() == "auto":
        return None
    return parse_coord(value, size)


def _parse_viewbox(el):
    raw = el.get("viewBox")
    if not raw:
        return None
    values = [float(part) for part in _FLOAT_RE.findall(raw)]
    if len(values) != 4:
        return None
    return tuple(values)


def _svg_viewport_matrix(el, parent_rect, nested, scene_scale_length=1.0):
    """Replicate Blender io_curve_svg's SVG viewport matrix and child rect."""
    parent_w, parent_h = parent_rect
    x = parse_coord(el.get("x", "0"), parent_w)
    y = parse_coord(el.get("y", "0"), parent_h)
    width_attr = el.get("width")
    height_attr = el.get("height")
    width = parse_coord(width_attr, parent_w) if width_attr else parent_w
    height = parse_coord(height_attr, parent_h) if height_attr else parent_h

    matrix = mat_translate(x, y)
    if nested and parent_w != 0 and parent_h != 0:
        matrix = mat_mul(matrix, mat_scale(width / parent_w, height / parent_h))

    viewbox = _parse_viewbox(el)
    if viewbox is not None:
        vx, vy, vw, vh = viewbox
        if vw != 0 and vh != 0:
            if nested or (width != 0 and height != 0):
                scale = min(width / vw, height / vh)
            else:
                scale = 1.0
                width, height = vw, vh
            tx = (width - vw * scale) / 2.0
            ty = (height - vh * scale) / 2.0
            matrix = mat_mul(matrix, mat_translate(tx, ty))
            matrix = mat_mul(matrix, mat_translate(-vx, -vy))
            matrix = mat_mul(matrix, mat_scale(scale, scale))

        unit = ""
        if height_attr:
            match = _FLOAT_RE.match(height_attr.strip())
            if match:
                unit = height_attr.strip()[match.end() :].strip()
        if unit in ("cm", "mm", "in", "pt", "pc"):
            unitscale = SVG_UNITS[unit] / 90.0 * 1000.0 / 39.3701
            unitscale /= scene_scale_length or 1.0
            matrix = mat_mul(matrix, mat_scale(unitscale, unitscale))

        # This is a Blender importer convention, including for nested SVGs.
        matrix = mat_mul(matrix, mat_translate(0.0, -vy - vh))
        child_rect = (vw, vh)
    else:
        child_rect = (width, height)

    return matrix, child_rect


def _root_matrix(root, scene_scale_length=1.0):
    """Compatibility wrapper returning the root viewport matrix."""
    matrix, _rect = _svg_viewport_matrix(
        root, (0.0, 0.0), nested=False, scene_scale_length=scene_scale_length
    )
    return matrix


def _warn_once(warnings, message):
    if message not in warnings:
        warnings.append(message)


def _style_map(el):
    declarations = {}
    for declaration in (el.get("style") or "").split(";"):
        if ":" not in declaration:
            continue
        key, value = declaration.split(":", 1)
        important_match = re.search(
            r"\s*!\s*important\s*$", value, flags=re.IGNORECASE
        )
        important = important_match is not None
        if important_match:
            value = value[: important_match.start()]
        key = key.strip().lower()
        previous = declarations.get(key)
        if previous is None or important or not previous[1]:
            declarations[key] = (value.strip(), important)
    return {key: value for key, (value, _important) in declarations.items()}


def _property(el, styles, name):
    return styles.get(name, el.get(name))


def _parse_opacity(value):
    if value is None or value.strip().lower() == "inherit":
        return 1.0
    raw = value.strip()
    try:
        parsed = float(raw[:-1]) / 100.0 if raw.endswith("%") else float(raw)
    except ValueError:
        return 1.0
    return max(0.0, min(1.0, parsed))


def _element_state(el, parent_state):
    styles = _style_map(el)
    display_value = (_property(el, styles, "display") or "inline").strip().lower()
    if display_value == "inherit":
        display = parent_state["display"]
    elif display_value in {"initial", "unset", "revert", "revert-layer"}:
        display = "inline"
    else:
        display = display_value
    if not parent_state["displayed"] or display == "none":
        return None

    visibility_value = _property(el, styles, "visibility")
    visibility = parent_state["visibility"]
    if visibility_value:
        visibility_value = visibility_value.strip().lower()
        if visibility_value in {"initial", "revert", "revert-layer"}:
            visibility = "visible"
        elif visibility_value not in {"inherit", "unset"}:
            visibility = visibility_value

    opacity_value = _property(el, styles, "opacity")
    if opacity_value:
        opacity_value = opacity_value.strip().lower()
    if opacity_value == "inherit":
        local_opacity = parent_state["local_opacity"]
    elif opacity_value in {"initial", "unset", "revert", "revert-layer"}:
        local_opacity = 1.0
    else:
        local_opacity = _parse_opacity(opacity_value)
    opacity = parent_state["opacity"] * local_opacity
    effects = set(parent_state["effects"])
    for name in ("clip-path", "mask", "filter"):
        value = _property(el, styles, name)
        if value and value.strip().lower() != "none":
            effects.add(name)

    return {
        "displayed": True,
        "display": display,
        "visibility": visibility,
        "opacity": opacity,
        "local_opacity": local_opacity,
        "effects": frozenset(effects),
        "styles": styles,
    }


def _resource_state():
    return {"items": {}, "total_bytes": 0, "placements": 0}


def _cache_resource(state, key, value):
    state["items"][key] = value
    return value


def _within_directory(path, directory):
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def _external_path(href, svg_dir, warnings, allow_outside):
    if svg_dir is None:
        _warn_once(warnings, "Skipped external image because the SVG directory is unknown")
        return None

    if _WINDOWS_PATH_RE.match(href):
        decoded_path = urllib.parse.unquote(href)
    else:
        parsed = urllib.parse.urlsplit(href)
        scheme = parsed.scheme.lower()
        if scheme and scheme != "file":
            warnings.append(f"Unsupported image URI scheme: {scheme}")
            return None
        if scheme == "file":
            # url2pathname performs the percent decoding itself.
            decoded_path = urllib.request.url2pathname(parsed.path)
            if parsed.netloc and parsed.netloc.lower() != "localhost":
                decoded_path = f"//{parsed.netloc}{decoded_path}"
        else:
            decoded_path = urllib.parse.unquote(parsed.path)

    path = Path(decoded_path)
    if not path.is_absolute():
        path = Path(svg_dir) / path
    try:
        resolved = path.resolve()
        svg_root = Path(svg_dir).resolve()
    except OSError:
        warnings.append(f"Could not resolve image reference: {href[:80]}")
        return None

    if not allow_outside and not _within_directory(resolved, svg_root):
        warnings.append(
            f"Blocked image reference outside the SVG directory: {href[:80]}"
        )
        return None
    return resolved


def _decode_href(
    href,
    svg_dir,
    warnings,
    resources=None,
    allow_external_outside_svg=False,
):
    """Return decoded ``(bytes, extension)`` with caching and safety limits."""
    resources = resources or _resource_state()
    href = href.strip()
    if href in resources["items"]:
        return resources["items"][href]

    if href.lower().startswith("data:"):
        match = _DATA_URI_RE.fullmatch(href)
        if not match:
            warnings.append("Skipped image with malformed data URI")
            return _cache_resource(resources, href, (None, None))
        mime = match.group("mime").strip().lower()
        params = match.group("params").lower()
        try:
            if "base64" in params:
                encoded = urllib.parse.unquote(match.group("data"))
                encoded = re.sub(r"\s+", "", encoded)
                if len(encoded) * 3 // 4 > MAX_IMAGE_BYTES:
                    raise ValueError("image exceeds the per-resource size limit")
                data = base64.b64decode(encoded, validate=True)
            else:
                data = urllib.parse.unquote_to_bytes(match.group("data"))
        except (ValueError, UnicodeError):
            warnings.append("Skipped image with undecodable data URI")
            return _cache_resource(resources, href, (None, None))
        extension = _MIME_EXTENSIONS.get(mime, ".png")
    else:
        path = _external_path(
            href, svg_dir, warnings, allow_external_outside_svg
        )
        if path is None:
            return _cache_resource(resources, href, (None, None))
        if not path.is_file():
            warnings.append(f"Could not resolve image reference: {href[:80]}")
            return _cache_resource(resources, href, (None, None))
        try:
            if path.stat().st_size > MAX_IMAGE_BYTES:
                warnings.append(f"Skipped oversized image reference: {href[:80]}")
                return _cache_resource(resources, href, (None, None))
            data = path.read_bytes()
        except OSError:
            warnings.append(f"Could not read image reference: {href[:80]}")
            return _cache_resource(resources, href, (None, None))
        extension = path.suffix or ".png"

    if len(data) > MAX_IMAGE_BYTES:
        warnings.append("Skipped image larger than the per-resource size limit")
        return _cache_resource(resources, href, (None, None))
    if resources["total_bytes"] + len(data) > MAX_TOTAL_IMAGE_BYTES:
        _warn_once(warnings, "Skipped images after reaching the total image size limit")
        return _cache_resource(resources, href, (None, None))

    resources["total_bytes"] += len(data)
    return _cache_resource(resources, href, (data, extension))


def _emit_image(
    el,
    ctm,
    viewport,
    state,
    images,
    warnings,
    svg_dir,
    resources,
    allow_external_outside_svg,
    marker_id=None,
):
    if state["visibility"] in {"hidden", "collapse"} or state["opacity"] <= 0:
        return None
    # SVG 2 plain href takes precedence when both forms are present.
    href = el.get("href")
    if href is None:
        href = el.get(XLINK_HREF)
    if not href:
        return None

    data, extension = _decode_href(
        href,
        svg_dir,
        warnings,
        resources,
        allow_external_outside_svg,
    )
    if data is None:
        return None

    styles = state["styles"]
    viewport_w, viewport_h = viewport
    width = _parse_image_length(_property(el, styles, "width"), viewport_w)
    height = _parse_image_length(_property(el, styles, "height"), viewport_h)
    if (width is not None and width <= 0) or (height is not None and height <= 0):
        return None
    x = parse_coord(_property(el, styles, "x") or "0", viewport_w)
    y = parse_coord(_property(el, styles, "y") or "0", viewport_h)

    if state["effects"]:
        _warn_once(
            warnings,
            "Image clipping, masking, and filters are not currently imported",
        )

    corners = None
    if width is not None and height is not None:
        corners = [
            mat_apply(ctm, point)
            for point in (
                (x, y),
                (x + width, y),
                (x + width, y + height),
                (x, y + height),
            )
        ]

    info = {
        "name": el.get("id") or f"Image{len(images) + 1}",
        "data": data,
        "ext": extension,
        "rect": (x, y, width, height),
        "matrix": ctm,
        "corners": corners,
        "preserve_aspect_ratio": el.get("preserveAspectRatio")
        or "xMidYMid meet",
        "opacity": state["opacity"],
        "marker_id": marker_id,
    }
    images.append(info)
    return info


# Definition-only and otherwise non-rendered containers.
_SKIP_TAGS = {
    "defs",
    "symbol",
    "clipPath",
    "mask",
    "marker",
    "pattern",
    "switch",
    "foreignObject",
    "style",
    "script",
    "metadata",
}


def _walk(
    el,
    ctm,
    viewport,
    parent_state,
    ids,
    images,
    warnings,
    svg_dir,
    resources,
    allow_external_outside_svg,
    scene_scale_length,
    marker_callback=None,
    depth=0,
):
    if depth > MAX_SVG_TRAVERSAL_DEPTH:
        _warn_once(warnings, "Skipped SVG content beyond the traversal depth limit")
        return
    if not isinstance(el.tag, str):
        return
    qname = etree.QName(el.tag)
    if qname.namespace not in (None, SVG_NS):
        return
    tag = qname.localname
    if tag in _SKIP_TAGS:
        return

    state = _element_state(el, parent_state)
    if state is None:
        return

    transform = el.get("transform")
    if transform:
        ctm = mat_mul(ctm, parse_transform(transform))

    if tag == "svg":
        viewport_matrix, viewport = _svg_viewport_matrix(
            el,
            viewport,
            nested=True,
            scene_scale_length=scene_scale_length,
        )
        ctm = mat_mul(ctm, viewport_matrix)

    if tag == "image":
        if resources["placements"] >= MAX_IMAGE_PLACEMENTS:
            _warn_once(warnings, "Skipped images after reaching the placement limit")
            return
        resources["placements"] += 1
        marker_id = marker_callback(el) if marker_callback else None
        _emit_image(
            el,
            ctm,
            viewport,
            state,
            images,
            warnings,
            svg_dir,
            resources,
            allow_external_outside_svg,
            marker_id,
        )
        return

    if tag == "use":
        href = el.get("href")
        if href is None:
            href = el.get(XLINK_HREF)
        if not href or not href.startswith("#"):
            return
        target = ids.get(href[1:])
        if target is None:
            return
        x = parse_coord(el.get("x", "0"), viewport[0])
        y = parse_coord(el.get("y", "0"), viewport[1])
        ctm = mat_mul(ctm, mat_translate(x, y))
        target_tag = etree.QName(target.tag).localname
        if target_tag in {"symbol", "svg"}:
            # Match flatten_svg: these containers contribute their children.
            for child in list(target):
                _walk(
                    child,
                    ctm,
                    viewport,
                    state,
                    ids,
                    images,
                    warnings,
                    svg_dir,
                    resources,
                    allow_external_outside_svg,
                    scene_scale_length,
                    marker_callback,
                    depth + 1,
                )
        else:
            _walk(
                target,
                ctm,
                viewport,
                state,
                ids,
                images,
                warnings,
                svg_dir,
                resources,
                allow_external_outside_svg,
                scene_scale_length,
                marker_callback,
                depth + 1,
            )
        return

    if tag not in {"svg", "g", "a"}:
        return
    for child in list(el):
        _walk(
            child,
            ctm,
            viewport,
            state,
            ids,
            images,
            warnings,
            svg_dir,
            resources,
            allow_external_outside_svg,
            scene_scale_length,
            marker_callback,
            depth + 1,
        )


def _extract_svg_images(
    svg_content,
    svg_dir=None,
    scene_scale_length=1.0,
    allow_external_outside_svg=False,
    add_markers=False,
):
    root = parse_svg_string(svg_content)
    ids = {}
    existing_ids = set()
    has_embedded_stylesheet = False
    has_image_element = False
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        qname = etree.QName(el.tag)
        if qname.namespace in (None, SVG_NS):
            has_embedded_stylesheet |= qname.localname == "style"
            has_image_element |= qname.localname == "image"
        element_id = el.get("id")
        if element_id:
            ids[element_id] = el
            existing_ids.add(element_id)

    images = []
    warnings = []
    if has_embedded_stylesheet and has_image_element:
        warnings.append(
            "Embedded CSS stylesheets are not evaluated for image visibility "
            "or opacity"
        )
    resources = _resource_state()
    root_matrix, root_rect = _svg_viewport_matrix(
        root,
        (0.0, 0.0),
        nested=False,
        scene_scale_length=scene_scale_length,
    )
    root_state = _element_state(
        root,
        {
            "displayed": True,
            "display": "inline",
            "visibility": "visible",
            "opacity": 1.0,
            "local_opacity": 1.0,
            "effects": frozenset(),
            "styles": {},
        },
    )

    marker_ids = []
    marker_prefix = f"__ESVG_IMG_{uuid.uuid4().hex[:12]}_"
    while any(value.startswith(marker_prefix) for value in existing_ids):
        marker_prefix = f"_{marker_prefix}"

    def add_marker(image_el):
        marker_id = f"{marker_prefix}{len(marker_ids):06d}"
        marker_ids.append(marker_id)
        namespace = etree.QName(image_el.tag).namespace
        marker_tag = f"{{{namespace}}}line" if namespace else "line"
        marker = etree.Element(marker_tag)
        marker.set("id", marker_id)
        marker.set("x1", "0")
        marker.set("y1", "0")
        marker.set("x2", "0")
        marker.set("y2", "0")
        parent = image_el.getparent()
        if parent is not None:
            parent.replace(image_el, marker)
        return marker_id

    if root_state is not None:
        for child in list(root):
            _walk(
                child,
                root_matrix,
                root_rect,
                root_state,
                ids,
                images,
                warnings,
                svg_dir,
                resources,
                allow_external_outside_svg,
                scene_scale_length,
                add_marker if add_markers else None,
            )

    marked_svg = (
        etree.tostring(root, encoding="unicode", pretty_print=True)
        if add_markers
        else None
    )
    return images, warnings, marked_svg, marker_ids


def extract_svg_images(
    svg_content,
    svg_dir=None,
    scene_scale_length=1.0,
    allow_external_outside_svg=False,
):
    """Return rendered image placements and warnings from SVG content."""
    images, warnings, _marked_svg, _marker_ids = _extract_svg_images(
        svg_content,
        svg_dir,
        scene_scale_length,
        allow_external_outside_svg,
        add_markers=False,
    )
    return images, warnings


def prepare_svg_images(
    processed_svg,
    svg_dir=None,
    scene_scale_length=1.0,
    allow_external_outside_svg=False,
):
    """Extract images and return an import SVG containing paint-order markers."""
    return _extract_svg_images(
        processed_svg,
        svg_dir,
        scene_scale_length,
        allow_external_outside_svg,
        add_markers=True,
    )


# --- Blender-side image datablocks, materials, geometry, and paint order ---


def _load_packed_image(info, cache, warnings):
    import bpy

    key = hashlib.sha256(info["data"]).hexdigest()
    if key in cache:
        return cache[key]

    image = None
    tmp = tempfile.NamedTemporaryFile(suffix=info["ext"], delete=False)
    try:
        tmp.write(info["data"])
        tmp.close()
        image = bpy.data.images.load(tmp.name, check_existing=False)
        image.name = info["name"]
        image.pack()
        image.filepath = ""
        image["typst_svg_source_hash"] = key
    except (OSError, RuntimeError) as exc:
        warnings.append(f"Could not load image {info['name']}: {exc}")
        if image is not None and image.users == 0:
            bpy.data.images.remove(image)
        return None
    finally:
        try:
            tmp.close()
            os.unlink(tmp.name)
        except OSError:
            pass

    cache[key] = image
    return image


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
    if len(tokens) > 2 or (len(tokens) == 2 and tokens[1] not in {"meet", "slice"}):
        return "xMidYMid", "meet"
    mode = tokens[1] if len(tokens) == 2 else "meet"
    return align, mode


def _align_factor(align, axis):
    part = align.split("Y", 1)[0][1:] if axis == "x" else align.split("Y", 1)[1]
    return {"Min": 0.0, "Mid": 0.5, "Max": 1.0}.get(part, 0.5)


def _placement_geometry(info, image_size):
    """Return transformed corners and per-vertex UVs for an image placement."""
    if "rect" not in info or "matrix" not in info:
        return info.get("corners"), [(0, 1), (1, 1), (1, 0), (0, 0)]

    image_w, image_h = (float(image_size[0]), float(image_size[1]))
    if image_w <= 0 or image_h <= 0:
        return None, None
    x, y, width, height = info["rect"]
    if width is None and height is None:
        width, height = image_w, image_h
    elif width is None:
        width = height * image_w / image_h
    elif height is None:
        height = width * image_h / image_w
    if width <= 0 or height <= 0:
        return None, None

    align, mode = _parse_preserve_aspect_ratio(info.get("preserve_aspect_ratio"))
    uvs = [(0, 1), (1, 1), (1, 0), (0, 0)]
    if align == "none":
        local_x, local_y, local_w, local_h = x, y, width, height
    else:
        scale = (
            max(width / image_w, height / image_h)
            if mode == "slice"
            else min(width / image_w, height / image_h)
        )
        scaled_w = image_w * scale
        scaled_h = image_h * scale
        x_factor = _align_factor(align, "x")
        y_factor = _align_factor(align, "y")
        if mode == "meet":
            local_x = x + (width - scaled_w) * x_factor
            local_y = y + (height - scaled_h) * y_factor
            local_w, local_h = scaled_w, scaled_h
        else:
            local_x, local_y, local_w, local_h = x, y, width, height
            crop_x = max(0.0, scaled_w - width) * x_factor
            crop_y = max(0.0, scaled_h - height) * y_factor
            u0 = crop_x / scaled_w
            u1 = (crop_x + width) / scaled_w
            top = crop_y / scaled_h
            bottom = (crop_y + height) / scaled_h
            uvs = [
                (u0, 1.0 - top),
                (u1, 1.0 - top),
                (u1, 1.0 - bottom),
                (u0, 1.0 - bottom),
            ]

    local_corners = (
        (local_x, local_y),
        (local_x + local_w, local_y),
        (local_x + local_w, local_y + local_h),
        (local_x, local_y + local_h),
    )
    return [mat_apply(info["matrix"], point) for point in local_corners], uvs


def _create_image_material(image, use_emission):
    import bpy

    mat = bpy.data.materials.new(name=f"MatImg_{image.name}")
    mat["typst_svg_image_material"] = True
    mat["typst_svg_use_emission"] = bool(use_emission)
    mat.use_nodes = True
    mat.blend_method = "BLEND"
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    tex = nodes.new(type="ShaderNodeTexImage")
    tex.image = image
    tex.extension = "CLIP"
    transparent = nodes.new(type="ShaderNodeBsdfTransparent")
    shader = nodes.new(
        type="ShaderNodeEmission" if use_emission else "ShaderNodeBsdfDiffuse"
    )
    if use_emission:
        shader.inputs["Strength"].default_value = 1.0
    attribute = nodes.new(type="ShaderNodeAttribute")
    attribute.attribute_name = "opacity"
    attribute.attribute_type = "OBJECT"
    multiply = nodes.new(type="ShaderNodeMath")
    multiply.operation = "MULTIPLY"
    mix_shader = nodes.new(type="ShaderNodeMixShader")
    output = nodes.new(type="ShaderNodeOutputMaterial")

    tex.location = (-700, 50)
    attribute.location = (-700, 350)
    multiply.location = (-400, 300)
    transparent.location = (-150, 200)
    shader.location = (-150, 0)
    mix_shader.location = (100, 100)
    output.location = (350, 100)

    links.new(tex.outputs["Color"], shader.inputs["Color"])
    links.new(tex.outputs["Alpha"], multiply.inputs[0])
    links.new(attribute.outputs["Fac"], multiply.inputs[1])
    links.new(multiply.outputs[0], mix_shader.inputs["Fac"])
    links.new(transparent.outputs[0], mix_shader.inputs[1])
    links.new(shader.outputs[0], mix_shader.inputs[2])
    links.new(mix_shader.outputs[0], output.inputs["Surface"])
    return mat


def create_image_planes(
    images,
    collection,
    use_emission=False,
    warnings=None,
    scale_factor=1.0,
):
    """Create packed, UV-mapped image planes for extracted placements."""
    import bpy

    warnings = warnings if warnings is not None else []
    created = []
    image_cache = {}
    material_cache = {}
    for info in images:
        image = _load_packed_image(info, image_cache, warnings)
        if image is None:
            continue
        corners, corner_uvs = _placement_geometry(info, image.size)
        if not corners:
            warnings.append(f"Skipped image with invalid geometry: {info['name']}")
            continue

        verts = [
            (
                x * BLENDER_SCALE * scale_factor,
                -y * BLENDER_SCALE * scale_factor,
                0.0,
            )
            for x, y in corners
        ]
        area = sum(
            verts[index][0] * verts[(index + 1) % 4][1]
            - verts[(index + 1) % 4][0] * verts[index][1]
            for index in range(4)
        )
        if abs(area) < 1e-18:
            warnings.append(f"Skipped degenerate image placement: {info['name']}")
            continue
        loop_order = (0, 1, 2, 3) if area > 0 else (0, 3, 2, 1)

        mesh = bpy.data.meshes.new(f"Image_{info['name']}")
        mesh["typst_svg_image_mesh"] = True
        mesh.from_pydata(verts, [], [loop_order])
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for loop in mesh.loops:
            uv_layer.data[loop.index].uv = corner_uvs[loop.vertex_index]

        material_key = (image.as_pointer(), bool(use_emission))
        material = material_cache.get(material_key)
        if material is None:
            material = _create_image_material(image, use_emission)
            material_cache[material_key] = material
        mesh.materials.append(material)

        obj = bpy.data.objects.new(f"Image_{info['name']}", mesh)
        obj["typst_svg_image_object"] = True
        collection.objects.link(obj)
        obj["opacity"] = float(info.get("opacity", 1.0))
        obj.id_properties_ui("opacity").update(min=0.0, max=1.0, step=0.1)
        if info.get("marker_id"):
            obj["svg_marker_id"] = info["marker_id"]
        info["_created_object"] = obj
        created.append(obj)

    for image in tuple(image_cache.values()):
        if image.users == 0:
            bpy.data.images.remove(image)
    return created


def _marker_id_for_object(obj_name, marker_ids):
    if obj_name in marker_ids:
        return obj_name
    match = _BLENDER_SUFFIX_RE.match(obj_name)
    if match and match.group(1) in marker_ids:
        return match.group(1)
    return None


def _remove_image_plane(obj):
    """Remove one generated plane and any now-unused generated data-blocks."""
    import bpy

    mesh = obj.data
    materials = {material for material in mesh.materials if material is not None}
    images = set()
    for material in materials:
        if not material.use_nodes or material.node_tree is None:
            continue
        for node in material.node_tree.nodes:
            image = getattr(node, "image", None)
            if image is not None:
                images.add(image)

    bpy.data.objects.remove(obj, do_unlink=True)
    if mesh.users == 0:
        bpy.data.meshes.remove(mesh)
    for material in materials:
        if material.users == 0 and material.get("typst_svg_image_material"):
            bpy.data.materials.remove(material)
    for image in images:
        if image.users == 0 and image.get("typst_svg_source_hash"):
            bpy.data.images.remove(image)


def finalize_paint_order(
    collection,
    source_objects,
    images,
    marker_ids,
    warnings=None,
    z_step=PAINT_ORDER_Z_STEP,
):
    """Replace marker curves with planes and restore logical collection order."""
    import bpy

    warnings = warnings if warnings is not None else []
    marker_set = set(marker_ids)
    image_by_marker = {
        info["marker_id"]: info
        for info in images
        if info.get("marker_id") is not None
    }
    ordered = []
    found_markers = set()

    for obj in source_objects:
        marker_id = _marker_id_for_object(obj.name, marker_set)
        if marker_id is None:
            ordered.append(obj)
            continue
        found_markers.add(marker_id)
        info = image_by_marker.get(marker_id)
        if info is not None and info.get("_created_object") is not None:
            ordered.append(info["_created_object"])
        data = obj.data
        materials = (
            {material for material in data.materials if material is not None}
            if data is not None and hasattr(data, "materials")
            else set()
        )
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and data.users == 0:
            bpy.data.curves.remove(data)
        for material in materials:
            if material.users == 0 and (
                material.get("typst_svg_blender_material")
            ):
                bpy.data.materials.remove(material)

    for info in images:
        obj = info.get("_created_object")
        if obj is not None and obj not in ordered:
            warnings.append(
                f"Skipped image because its paint-order marker was not imported: "
                f"{info['name']}"
            )
            _remove_image_plane(obj)
            info["_created_object"] = None

    missing = marker_set - found_markers
    if missing:
        _warn_once(warnings, "Some image paint-order markers were not imported")

    # Relinking is the supported way to restore collection.objects order.  It
    # also keeps the existing Z Offset panel consistent with SVG paint order.
    for obj in ordered:
        if obj.name in collection.objects:
            collection.objects.unlink(obj)
    for index, obj in enumerate(ordered):
        collection.objects.link(obj)
        obj["svg_paint_index"] = index
        obj.location.z = index * z_step

    for info in images:
        info.pop("_created_object", None)
    return ordered
