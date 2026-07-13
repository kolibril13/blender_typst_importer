"""Blender 5.2 coverage for import and Geometry Nodes utility workflows."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import bpy
import pytest

import typst_importer
from typst_importer.operators import textbox_import
from typst_importer.node_groups import (
    create_follow_curve_node_group,
    modifier_input,
)
from typst_importer.operators.path import configure_follow_path_animation
from typst_importer.operators.textbox_import import ImportFromTextboxAsCurveOperator
from typst_importer.operators.visibility import toggle_visibility
from typst_importer.typst_to_svg import deduplicate_materials, typst_express


pytestmark = pytest.mark.skipif(
    bpy.app.version < (5, 2, 0),
    reason="These workflows require Blender 5.2 or newer",
)


@pytest.fixture(autouse=True)
def clean_blender_data():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.frame_set(1)
    yield
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _fcurve_frames(obj: bpy.types.Object, data_path: str) -> list[float]:
    action = obj.animation_data.action
    slot = obj.animation_data.action_slot
    fcurve = next(
        curve
        for layer in action.layers
        for strip in layer.strips
        for curve in strip.channelbag(slot).fcurves
        if curve.data_path == data_path
    )
    return [point.co.x for point in fcurve.keyframe_points]


def test_visibility_uses_typed_modifier_input_and_keyframes():
    mesh = bpy.data.meshes.new("VisibilityMesh")
    obj = bpy.data.objects.new("VisibilityObject", mesh)
    bpy.context.scene.collection.objects.link(obj)

    modifier = toggle_visibility(obj, current_frame=5, make_visible=True)
    input_value, socket = modifier_input(modifier, "Visibility")

    assert input_value.type == "VALUE"
    assert input_value.value is False
    data_path = f'modifiers["{modifier.name}"].properties.inputs.{socket.identifier}.value'
    assert _fcurve_frames(obj, data_path) == [4.0, 5.0]


def test_follow_path_uses_typed_object_and_factor_inputs():
    mesh = bpy.data.meshes.new("FollowerMesh")
    follower = bpy.data.objects.new("Follower", mesh)
    bpy.context.scene.collection.objects.link(follower)

    curve_data = bpy.data.curves.new("Path", type="CURVE")
    path = bpy.data.objects.new("Path", curve_data)
    bpy.context.scene.collection.objects.link(path)
    spline = curve_data.splines.new("POLY")
    spline.points.add(1)
    spline.points[0].co = (0.0, 0.0, 0.0, 1.0)
    spline.points[1].co = (2.0, 0.0, 0.0, 1.0)

    modifier = follower.modifiers.new("FollowPath", type="NODES")
    modifier.node_group = create_follow_curve_node_group()
    configure_follow_path_animation(follower, modifier, path, current_frame=3)

    follow_path_nodes = modifier.node_group.nodes
    assert follow_path_nodes["Object Info"].location.x < follow_path_nodes[
        "Sample Curve"
    ].location.x
    assert follow_path_nodes["Sample Curve"].location.x < follow_path_nodes[
        "Transform Geometry"
    ].location.x

    object_input, _ = modifier_input(modifier, "Object")
    factor_input, factor_socket = modifier_input(modifier, "Factor")
    assert object_input.type == "VALUE"
    assert object_input.value == path
    assert factor_input.type == "VALUE"
    assert factor_input.value == pytest.approx(0.0)
    factor_path = (
        f'modifiers["{modifier.name}"].properties.inputs.'
        f"{factor_socket.identifier}.value"
    )
    assert _fcurve_frames(follower, factor_path) == [3.0, 13.0]

    configure_follow_path_animation(follower, modifier, path, current_frame=8)
    assert _fcurve_frames(follower, factor_path) == [8.0, 18.0]


@pytest.mark.parametrize(
    ("kwargs", "object_type", "fill_mode"),
    [
        ({"convert_to_mesh": False}, "CURVE", "BOTH"),
        ({}, "MESH", None),
        (
            {"convert_to_mesh": False, "convert_to_unfilled_path": True},
            "CURVE",
            "NONE",
        ),
    ],
)
def test_typst_import_modes(kwargs, object_type, fill_mode):
    collection = typst_express(
        '#rect(width: 12pt, height: 12pt, fill: rgb("#336699"))',
        name=f"pytest_{object_type}_{fill_mode}",
        **kwargs,
    )

    objects = list(collection.objects)
    assert objects
    assert {obj.type for obj in objects} == {object_type}
    if fill_mode is not None:
        assert all(obj.data.fill_mode == fill_mode for obj in objects)


def test_material_deduplication_preserves_unrelated_orphan_data():
    unrelated_material = bpy.data.materials.new("KeepThisMaterial")
    collection = bpy.data.collections.new("MaterialDedup")
    bpy.context.scene.collection.children.link(collection)

    curve = bpy.data.curves.new("ImportedCurve", type="CURVE")
    material = bpy.data.materials.new("ImportedMaterial")
    curve.materials.append(material)
    collection.objects.link(bpy.data.objects.new("ImportedCurve", curve))

    deduplicate_materials(collection)

    assert bpy.data.materials.get(unrelated_material.name) == unrelated_material


def test_textbox_curve_importer_smoke_test(tmp_path: Path):
    typst_file = tmp_path / "textbox_input.typ"
    typst_file.write_text('#rect(width: 12pt, height: 12pt, fill: rgb("#336699"))')

    collection = ImportFromTextboxAsCurveOperator.import_typst(
        None,
        typst_file,
    )

    assert collection.objects
    assert {obj.type for obj in collection.objects} == {"CURVE"}


def test_textbox_import_prepends_the_header_displayed_in_the_panel():
    captured = {}

    def fake_typst_import(typst_file, **_kwargs):
        captured["content"] = typst_file.read_text()
        return SimpleNamespace(name="Test Collection")

    bpy.context.scene.typst_text = "#text[Hello]"
    bpy.context.window_manager.typst_use_custom_header = True
    bpy.context.window_manager.typst_custom_header = "#set text(size: 24pt)\n"

    operator = SimpleNamespace(
        import_typst=lambda typst_file, _origin_to_char: fake_typst_import(typst_file),
        report=lambda _level, _message: None,
    )
    result = textbox_import.ImportFromTextboxOperator.execute(operator, bpy.context)

    assert result == {"FINISHED"}
    assert captured["content"] == "#set text(size: 24pt)\n#text[Hello]"


def test_addon_registers_and_unregisters_cleanly():
    typst_importer.register()
    try:
        assert hasattr(bpy.ops.import_scene, "import_textbox_grease_pencil")
        assert hasattr(bpy.ops.export_scene, "typst_svg")
    finally:
        typst_importer.unregister()
