"""Blender 5.2 coverage for SVG raster images produced by Typst."""

from __future__ import annotations

import base64
from pathlib import Path
import struct
import zlib

import bpy
import pytest

from typst_importer.image_import import extract_svg_images
from typst_importer.svg_preprocessing import SVG_NS, preprocess_svg
from typst_importer.typst_to_svg import typst_to_blender_curves


pytestmark = pytest.mark.skipif(
    bpy.app.version < (5, 2, 0),
    reason="These workflows require Blender 5.2 or newer",
)


def _png_bytes(width=1, height=1):
    def chunk(kind, data):
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    row = b"\x00" + b"\xff\x40\x20\xff" * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk("IHDR".encode(), struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk("IDAT".encode(), zlib.compress(row * height))
        + chunk("IEND".encode(), b"")
    )


def _data_uri(width=1, height=1):
    return "data:image/png;base64," + base64.b64encode(
        _png_bytes(width, height)
    ).decode("ascii")


def test_preprocessing_extracts_embedded_use_image_with_viewport_geometry():
    svg = f'''<svg xmlns="{SVG_NS}" width="100" height="100">
      <defs><symbol id="asset" viewBox="0 0 10 20"
        preserveAspectRatio="none">
        <image width="10" height="20" preserveAspectRatio="none"
          href="{_data_uri()}"/>
      </symbol></defs>
      <use href="#asset" x="4" y="5" width="40" height="60"/>
    </svg>'''

    images, warnings = extract_svg_images(preprocess_svg(svg))

    assert warnings == []
    assert len(images) == 1
    xs = [corner[0] for corner in images[0]["corners"]]
    ys = [corner[1] for corner in images[0]["corners"]]
    assert min(xs) == pytest.approx(4.0)
    assert max(xs) == pytest.approx(44.0)
    assert min(ys) == pytest.approx(5.0)
    assert max(ys) == pytest.approx(65.0)


def test_external_images_are_contained_to_the_typst_source_folder(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    outside_image = tmp_path / "outside.png"
    outside_image.write_bytes(_png_bytes())
    svg = f'''<svg xmlns="{SVG_NS}" width="10" height="10">
      <image width="10" height="10" href="../outside.png"/>
    </svg>'''

    images, warnings = extract_svg_images(
        preprocess_svg(svg),
        svg_dir=source_dir,
    )

    assert images == []
    assert any("outside the SVG directory" in warning for warning in warnings)


def test_preprocessing_bounds_recursive_use_expansion():
    svg = f'''<svg xmlns="{SVG_NS}" width="10" height="10">
      <defs><g id="loop">
        <use href="#loop"/><use href="#loop"/><use href="#loop"/>
      </g></defs>
      <use href="#loop"/>
    </svg>'''

    with pytest.raises(ValueError, match="expansion limit"):
        preprocess_svg(svg)


def test_typst_image_becomes_a_packed_textured_plane(tmp_path: Path):
    image_file = tmp_path / "pixel.png"
    image_file.write_bytes(_png_bytes())
    typst_file = tmp_path / "image.typ"
    typst_file.write_text(
        "#set page(width: auto, height: auto, margin: 0pt, fill: none)\n"
        '#rect(width: 20pt, height: 20pt, fill: rgb("#336699"))\n'
        '#image("pixel.png", width: 20pt)\n',
        encoding="utf-8",
    )

    collection = typst_to_blender_curves(
        typst_file,
        scale_factor=100.0,
        convert_to_mesh=False,
    )

    planes = [obj for obj in collection.objects if obj.type == "MESH"]
    assert len(planes) == 1
    plane = planes[0]
    assert plane.get("typst_svg_image_object") is True
    curves = [obj for obj in collection.objects if obj.type == "CURVE"]
    assert len(curves) == 1
    assert plane.get("svg_paint_index") > curves[0].get("svg_paint_index")
    assert plane.dimensions.x == pytest.approx(curves[0].dimensions.x, abs=2e-6)
    assert plane.dimensions.y == pytest.approx(curves[0].dimensions.y, abs=2e-6)
    material = plane.data.materials[0]
    texture = next(
        node
        for node in material.node_tree.nodes
        if node.bl_idname == "ShaderNodeTexImage"
    )
    assert texture.image.packed_file
    assert not any(
        obj.name.startswith("__ESVG_IMG_") for obj in bpy.data.objects
    )
    assert not any(
        material.get("typst_svg_blender_material") and material.users == 0
        for material in bpy.data.materials
    )
