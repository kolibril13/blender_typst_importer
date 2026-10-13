"""Overlapping glyph contours must be merged before Blender fills them."""

from __future__ import annotations

import re

import bmesh
import bpy
import pathops
import pytest

from typst_importer.typst_to_svg import typst_express
from typst_importer.svg_preprocessing import (
    _svg_d_to_skia_path,
    remove_fill_overlaps,
)


def _svg(path_attributes: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">'
        f"<path {path_attributes}/></svg>"
    )


def _even_odd_area(d_attr: str) -> float:
    """Area as Blender fills it: even-odd, without resolving overlaps."""
    path = _svg_d_to_skia_path(d_attr)
    path.fillType = pathops.FillType.EVEN_ODD
    path.simplify()
    return abs(path.area)


def _single_path_d(svg_content: str) -> str:
    return re.search(r' d="([^"]+)"', svg_content).group(1)


# Two squares sharing a 5x5 corner, like the stem and arch of a font's "n".
OVERLAPPING_SQUARES = "M 0 0 L 10 0 L 10 10 L 0 10 Z M 5 5 L 15 5 L 15 15 L 5 15 Z"


def test_overlapping_contours_are_merged_for_even_odd_fill():
    assert _even_odd_area(OVERLAPPING_SQUARES) == pytest.approx(150.0)

    merged = _single_path_d(remove_fill_overlaps(_svg(f'd="{OVERLAPPING_SQUARES}"')))

    # The overlap is filled once, so even-odd now matches nonzero (175).
    assert _even_odd_area(merged) == pytest.approx(175.0)


def test_evenodd_paths_keep_their_holes():
    merged = _single_path_d(
        remove_fill_overlaps(
            _svg(f'd="{OVERLAPPING_SQUARES}" fill-rule="evenodd"')
        )
    )

    assert _even_odd_area(merged) == pytest.approx(150.0)


def test_unfilled_and_arc_paths_are_left_unchanged():
    unfilled = f'd="{OVERLAPPING_SQUARES}" fill="none"'
    arc = 'd="M 0 0 A 5 5 0 0 1 10 0 Z"'

    assert OVERLAPPING_SQUARES in remove_fill_overlaps(_svg(unfilled))
    assert "A 5 5 0 0 1 10 0" in remove_fill_overlaps(_svg(arc))


def _imported_mesh_area(content: str) -> float:
    collection = typst_express(content, name="pytest_overlap", convert_to_mesh=True)
    area = 0.0
    for obj in collection.objects:
        mesh = bmesh.new()
        mesh.from_mesh(obj.data)
        area += sum(face.calc_area() for face in mesh.faces)
        mesh.free()
    return area


def _typst_curve(*contours: tuple[tuple[int, int], ...]) -> str:
    """A single filled Typst curve with one closed polygon per contour."""
    parts = []
    for contour in contours:
        (x, y), *rest = contour
        parts.append(f"curve.move(({x}pt, {y}pt))")
        parts.extend(f"curve.line(({x}pt, {y}pt))" for x, y in rest)
        parts.append("curve.close()")
    return f"#curve(fill: black, {', '.join(parts)})"


SQUARE = ((0, 0), (10, 0), (10, 10), (0, 10))


@pytest.mark.parametrize(
    ("contours", "nonzero_area"),
    [
        # Two bars drawn in the same direction, like the overlapping stem and
        # arch of an "n". Blender's own fill doubled this area.
        (
            (
                ((0, 4), (20, 4), (20, 8), (0, 8)),
                ((8, 0), (12, 0), (12, 20), (8, 20)),
            ),
            144,
        ),
        # One outline crossing itself, like the bowl of a "g".
        (
            (((0, 0), (20, 0), (20, 10), (5, 10), (5, -5), (10, -5), (10, 5), (0, 5)),),
            200,
        ),
        # Opposite directions: nonzero leaves the overlap empty.
        (
            (SQUARE, ((5, 5), (5, 15), (15, 15), (15, 5))),
            150,
        ),
    ],
    ids=["same-direction-overlap", "self-crossing-outline", "opposite-direction-overlap"],
)
def test_overlapping_contours_import_with_the_rendered_area(contours, nonzero_area):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    square_area = _imported_mesh_area(_typst_curve(SQUARE))
    shape_area = _imported_mesh_area(_typst_curve(*contours))
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # The imported mesh must cover what Typst renders with the nonzero rule.
    assert shape_area / square_area == pytest.approx(nonzero_area / 100, rel=1e-3)
