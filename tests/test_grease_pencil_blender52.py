"""Blender 5.2 coverage for native Typst Grease Pencil conversion."""

from __future__ import annotations

import inspect

import bpy
import pytest

from typst_importer.typst_to_svg import (
    _convert_to_grease_pencil,
    typst_to_blender_curves,
    typst_express,
)


pytestmark = pytest.mark.skipif(
    bpy.app.version < (5, 2, 0),
    reason="Native Grease Pencil conversion requires Blender 5.2 or newer",
)


@pytest.fixture(autouse=True)
def clean_blender_data():
    """Give every test a deterministic empty file and remove all created data."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.frame_set(1)
    yield
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _new_collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def _new_filled_curve(
    collection: bpy.types.Collection,
    name: str,
    contours: list[list[tuple[float, float, float]]],
    color: tuple[float, float, float, float],
) -> bpy.types.Object:
    curve = bpy.data.curves.new(f"{name}Data", type="CURVE")
    curve.dimensions = "2D"
    curve.fill_mode = "BOTH"
    curve.resolution_u = 1

    for coordinates in contours:
        spline = curve.splines.new(type="POLY")
        spline.points.add(len(coordinates) - 1)
        for point, coordinate in zip(spline.points, coordinates, strict=True):
            point.co = (*coordinate, 1.0)
        spline.use_cyclic_u = True

    material = bpy.data.materials.new(f"{name}Material")
    material.diffuse_color = color
    curve.materials.append(material)

    obj = bpy.data.objects.new(name, curve)
    collection.objects.link(obj)
    return obj


def _attribute_values(drawing, name: str) -> list[object]:
    attribute = drawing.attributes.get(name)
    assert attribute is not None, f"Grease Pencil drawing has no {name!r} attribute"
    return [item.value for item in attribute.data]


def _drawing(obj: bpy.types.Object):
    assert isinstance(obj.data, bpy.types.GreasePencil)
    assert obj.data.layers.active is not None
    assert len(obj.data.layers.active.frames) == 1
    return obj.data.layers.active.frames[0].drawing


def _evaluated_drawing(obj: bpy.types.Object):
    # Direct RNA assignments made by a headless test need an explicit object
    # tag; Blender's modifier UI sends this update automatically.
    obj.update_tag()
    bpy.context.view_layer.update()
    evaluated_obj = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return _drawing(evaluated_obj)


def _interface_input(node_group, name: str):
    return next(
        item
        for item in node_group.interface.items_tree
        if item.item_type == "SOCKET"
        and item.in_out == "INPUT"
        and item.name == name
    )


def _stroke_radius_modifier(obj: bpy.types.Object):
    return next(
        modifier
        for modifier in obj.modifiers
        if modifier.type == "NODES" and modifier.name == "Typst Stroke Radius"
    )


def _modifier_radius_input(modifier):
    socket = _interface_input(modifier.node_group, "Stroke Radius")
    return getattr(modifier.properties.inputs, socket.identifier)


def test_native_conversion_preserves_holes_colors_and_unrelated_selection():
    imported = _new_collection("ImportedGlyphs")
    _new_filled_curve(
        imported,
        "Donut",
        contours=[
            [
                (-2.0, -2.0, 0.0),
                (2.0, -2.0, 0.0),
                (2.0, 2.0, 0.0),
                (-2.0, 2.0, 0.0),
            ],
            [
                (-1.0, -1.0, 0.0),
                (-1.0, 1.0, 0.0),
                (1.0, 1.0, 0.0),
                (1.0, -1.0, 0.0),
            ],
        ],
        color=(0.8, 0.2, 0.1, 0.65),
    )
    _new_filled_curve(
        imported,
        "Block",
        contours=[
            [
                (4.0, -1.0, 0.0),
                (6.0, -1.0, 0.0),
                (6.0, 1.0, 0.0),
                (4.0, 1.0, 0.0),
            ],
        ],
        color=(0.1, 0.3, 0.9, 1.0),
    )

    unrelated_mesh = bpy.data.meshes.new("UnrelatedMesh")
    unrelated_mesh.from_pydata(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        [],
        [(0, 1, 2)],
    )
    unrelated = bpy.data.objects.new("UnrelatedSelectedObject", unrelated_mesh)
    bpy.context.scene.collection.objects.link(unrelated)
    unrelated.select_set(True)
    bpy.context.view_layer.objects.active = unrelated
    unrelated_data_pointer = unrelated.data.as_pointer()

    _convert_to_grease_pencil(imported)

    assert unrelated.name in bpy.data.objects
    assert unrelated.type == "MESH"
    assert unrelated.select_get()
    assert unrelated.data.as_pointer() == unrelated_data_pointer
    assert len(unrelated.data.vertices) == 3

    converted = {obj.name: obj for obj in imported.objects}
    assert set(converted) == {"GP_Donut", "GP_Block"}
    assert {obj.type for obj in converted.values()} == {"GREASEPENCIL"}
    assert len(bpy.data.curves) == 0

    donut_drawing = _drawing(converted["GP_Donut"])
    assert len(donut_drawing.strokes) == 2
    assert [item.value for item in donut_drawing.curve_offsets] == [0, 4, 8]
    fill_id_attribute = donut_drawing.attributes["fill_id"]
    assert (fill_id_attribute.data_type, fill_id_attribute.domain) == (
        "INT",
        "CURVE",
    )
    fill_ids = _attribute_values(donut_drawing, "fill_id")
    assert fill_ids[0] == fill_ids[1]
    assert fill_ids[0] != 0
    hide_stroke_attribute = donut_drawing.attributes["hide_stroke"]
    assert (hide_stroke_attribute.data_type, hide_stroke_attribute.domain) == (
        "BOOLEAN",
        "CURVE",
    )
    assert _attribute_values(donut_drawing, "hide_stroke") == [True, True]
    assert _attribute_values(donut_drawing, "cyclic") == [True, True]

    expected_colors = {
        "GP_Donut": (0.8, 0.2, 0.1, 0.65),
        "GP_Block": (0.1, 0.3, 0.9, 1.0),
    }
    for name, expected_color in expected_colors.items():
        material = converted[name].data.materials[0]
        assert material.is_grease_pencil
        assert tuple(material.grease_pencil.fill_color) == pytest.approx(
            expected_color, abs=1e-6
        )
        assert tuple(material.grease_pencil.color) == pytest.approx(
            (0.0, 0.0, 0.0, 1.0), abs=1e-6
        )


def test_typst_express_grease_pencil_overrides_default_mesh_output():
    requested_radius = 0.08
    collection = typst_express(
        '#rect(width: 12pt, height: 12pt, fill: rgb("#336699"))',
        name="pytest_grease_pencil_expression",
        use_grease_pencil=True,
        grease_pencil_stroke_radius=requested_radius,
    )

    objects = list(collection.objects)
    assert objects
    assert {obj.type for obj in objects} == {"GREASEPENCIL"}
    assert not any(obj.type == "MESH" for obj in objects)
    assert all(obj.data.layers.active is not None for obj in objects)
    assert all(_attribute_values(_drawing(obj), "fill_id") for obj in objects)
    for obj in objects:
        modifier = _stroke_radius_modifier(obj)
        assert _modifier_radius_input(modifier).value == pytest.approx(
            requested_radius
        )
        evaluated = _evaluated_drawing(obj)
        assert _attribute_values(evaluated, "radius") == pytest.approx(
            [requested_radius] * len(evaluated.attributes["radius"].data)
        )


def test_stroke_radius_modifier_is_shared_adjustable_and_preserves_fill_ids():
    imported = _new_collection("StrokeRadiusGlyphs")
    _new_filled_curve(
        imported,
        "Donut",
        contours=[
            [
                (-2.0, -2.0, 0.0),
                (2.0, -2.0, 0.0),
                (2.0, 2.0, 0.0),
                (-2.0, 2.0, 0.0),
            ],
            [
                (-1.0, -1.0, 0.0),
                (-1.0, 1.0, 0.0),
                (1.0, 1.0, 0.0),
                (1.0, -1.0, 0.0),
            ],
        ],
        color=(0.1, 0.6, 0.8, 1.0),
    )
    _new_filled_curve(
        imported,
        "Block",
        contours=[
            [
                (4.0, -1.0, 0.0),
                (6.0, -1.0, 0.0),
                (6.0, 1.0, 0.0),
                (4.0, 1.0, 0.0),
            ],
        ],
        color=(0.9, 0.3, 0.1, 1.0),
    )

    _convert_to_grease_pencil(imported)

    converted = [obj for obj in imported.objects if obj.type == "GREASEPENCIL"]
    assert len(converted) == 2
    modifiers = [_stroke_radius_modifier(obj) for obj in converted]
    assert {modifier.name for modifier in modifiers} == {"Typst Stroke Radius"}
    assert len({modifier.node_group.as_pointer() for modifier in modifiers}) == 1

    node_group = modifiers[0].node_group
    assert node_group.name == "Typst Stroke Radius"
    radius_socket = _interface_input(node_group, "Stroke Radius")
    assert radius_socket.socket_type == "NodeSocketFloat"
    assert radius_socket.default_value == pytest.approx(0.01)

    set_radius_nodes = [
        node
        for node in node_group.nodes
        if node.bl_idname == "GeometryNodeSetCurveRadius"
    ]
    assert len(set_radius_nodes) == 1
    hide_stroke_nodes = [
        node
        for node in node_group.nodes
        if node.bl_idname == "GeometryNodeStoreNamedAttribute"
        and node.data_type == "BOOLEAN"
        and node.domain == "CURVE"
        and node.inputs["Name"].default_value == "hide_stroke"
    ]
    assert len(hide_stroke_nodes) == 1
    assert hide_stroke_nodes[0].inputs["Value"].default_value is False

    donut = next(obj for obj in converted if obj.name == "GP_Donut")
    source_fill_ids = _attribute_values(_drawing(donut), "fill_id")
    assert source_fill_ids[0] == source_fill_ids[1]
    assert source_fill_ids[0] != 0
    assert _attribute_values(_drawing(donut), "hide_stroke") == [True, True]

    donut_modifier = _stroke_radius_modifier(donut)
    modifier_input = getattr(
        donut_modifier.properties.inputs,
        radius_socket.identifier,
    )
    assert modifier_input.value == pytest.approx(radius_socket.default_value)
    assert modifier_input.type == "VALUE"
    evaluated = _evaluated_drawing(donut)
    assert _attribute_values(evaluated, "fill_id") == source_fill_ids
    assert _attribute_values(evaluated, "hide_stroke") == [False, False]
    assert _attribute_values(evaluated, "radius") == pytest.approx(
        [radius_socket.default_value] * len(evaluated.attributes["radius"].data)
    )

    adjusted_radius = radius_socket.default_value * 2.0
    modifier_input.value = adjusted_radius
    evaluated = _evaluated_drawing(donut)
    assert _attribute_values(evaluated, "radius") == pytest.approx(
        [adjusted_radius] * len(evaluated.attributes["radius"].data)
    )


def test_stroke_radius_group_is_shared_despite_a_name_collision():
    bpy.data.node_groups.new("Typst Stroke Radius", "ShaderNodeTree")
    imported = _new_collection("StrokeRadiusNameCollision")
    for name, offset in (("Left", 0.0), ("Right", 3.0)):
        _new_filled_curve(
            imported,
            name,
            contours=[
                [
                    (offset, 0.0, 0.0),
                    (offset + 2.0, 0.0, 0.0),
                    (offset + 2.0, 2.0, 0.0),
                    (offset, 2.0, 0.0),
                ]
            ],
            color=(0.2, 0.5, 0.8, 1.0),
        )

    _convert_to_grease_pencil(imported)

    node_groups = {
        _stroke_radius_modifier(obj).node_group.as_pointer()
        for obj in imported.objects
        if obj.type == "GREASEPENCIL"
    }
    assert len(node_groups) == 1
    generated_group = _stroke_radius_modifier(
        next(obj for obj in imported.objects if obj.type == "GREASEPENCIL")
    ).node_group
    assert generated_group.bl_idname == "GeometryNodeTree"
    assert generated_group.name.startswith("Typst Stroke Radius.")


def test_grease_pencil_options_do_not_shift_the_positional_api():
    for function in (typst_to_blender_curves, typst_express):
        parameters = inspect.signature(function).parameters
        assert parameters["position"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert parameters["show_indices"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert parameters["use_grease_pencil"].kind is inspect.Parameter.KEYWORD_ONLY
        assert (
            parameters["grease_pencil_stroke_radius"].kind
            is inspect.Parameter.KEYWORD_ONLY
        )
