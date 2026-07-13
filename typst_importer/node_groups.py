import bpy
from nodebpy import geometry as g


GREASE_PENCIL_STROKE_NODE_GROUP = "Typst Stroke Radius"
DEFAULT_GREASE_PENCIL_STROKE_RADIUS = 0.01
_GREASE_PENCIL_STROKE_NODE_GROUP_MARKER_KEY = "typst_importer_node_group"
_GREASE_PENCIL_STROKE_NODE_GROUP_MARKER = (
    "typst_importer.grease_pencil_stroke_radius.v1"
)


def _interface_input(node_group, name):
    """Return a named input socket from a node-group interface."""
    return next(
        (
            item
            for item in node_group.interface.items_tree
            if item.item_type == "SOCKET"
            and item.in_out == "INPUT"
            and item.name == name
        ),
        None,
    )


def modifier_input(modifier, socket_name):
    """Return a Geometry Nodes modifier input and its interface socket."""
    socket = _interface_input(modifier.node_group, socket_name)
    if socket is None:
        raise ValueError(
            f"Node group {modifier.node_group.name!r} has no {socket_name!r} input"
        )
    return getattr(modifier.properties.inputs, socket.identifier), socket


def set_modifier_input_value(modifier, socket_name, value):
    """Set a Geometry Nodes modifier input with Blender 5.2 typed RNA."""
    input_value, socket = modifier_input(modifier, socket_name)
    input_value.type = "VALUE"
    input_value.value = value
    return socket


def modifier_input_data_path(modifier, socket_name):
    """Return the Blender RNA path used to keyframe a modifier input."""
    _, socket = modifier_input(modifier, socket_name)
    return f'modifiers["{modifier.name}"].properties.inputs.{socket.identifier}.value'


def create_grease_pencil_stroke_radius_node_group():
    """Create the shared Blender 5.2 node group for Typst GP outlines."""
    for existing in bpy.data.node_groups:
        if (
            existing.get(_GREASE_PENCIL_STROKE_NODE_GROUP_MARKER_KEY)
            == _GREASE_PENCIL_STROKE_NODE_GROUP_MARKER
            and existing.bl_idname == "GeometryNodeTree"
            and _interface_input(existing, "Stroke Radius") is not None
        ):
            return existing

    with g.tree(GREASE_PENCIL_STROKE_NODE_GROUP, arrange="sugiyama") as tree:
        node_group = tree.tree
        node_group.is_modifier = True
        node_group.description = (
            "Show Typst Grease Pencil strokes and control their radius"
        )
        node_group[_GREASE_PENCIL_STROKE_NODE_GROUP_MARKER_KEY] = (
            _GREASE_PENCIL_STROKE_NODE_GROUP_MARKER
        )

        geometry = tree.inputs.geometry("Geometry")
        stroke_radius = tree.inputs.float(
            "Stroke Radius",
            DEFAULT_GREASE_PENCIL_STROKE_RADIUS,
            "Radius of the visible Grease Pencil stroke",
            min_value=0.0,
            max_value=10.0,
            subtype="DISTANCE",
        )
        geometry_output = tree.outputs.geometry("Geometry")

        show_stroke = g.StoreNamedAttribute.spline.boolean(
            geometry=geometry, name="hide_stroke", value=False
        )
        show_stroke.node.name = "Show Stroke"
        show_stroke.node.label = "Show Stroke"
        set_radius = g.SetCurveRadius(show_stroke, radius=stroke_radius)
        set_radius.node.name = "Set Stroke Radius"
        set_radius.node.label = "Set Stroke Radius"
        set_radius >> geometry_output

        tree.node_positions = {
            "Group Input": (-500.0, 0.0),
            "Show Stroke": (-260.0, 0.0),
            "Set Stroke Radius": (20.0, 0.0),
            "Group Output": (280.0, 0.0),
        }

    return node_group


def add_grease_pencil_stroke_radius_modifier(
    obj,
    stroke_radius=DEFAULT_GREASE_PENCIL_STROKE_RADIUS,
):
    """Attach the Typst stroke-radius Geometry Nodes modifier to an object."""
    if obj.type != "GREASEPENCIL":
        raise TypeError("Stroke-radius modifiers require a Grease Pencil object")
    if stroke_radius < 0.0:
        raise ValueError("Grease Pencil stroke radius must be non-negative")

    node_group = create_grease_pencil_stroke_radius_node_group()
    modifier = obj.modifiers.new(
        name=GREASE_PENCIL_STROKE_NODE_GROUP,
        type="NODES",
    )
    modifier.node_group = node_group
    set_modifier_input_value(modifier, "Stroke Radius", float(stroke_radius))
    return modifier


def create_follow_curve_node_group():
    """Create a Geometry Nodes group that makes an object follow a curve."""
    with g.tree("Follow Path", arrange="sugiyama") as tree:
        follow_path = tree.tree
        follow_path.color_tag = "NONE"
        follow_path.description = ""
        follow_path.default_group_node_width = 140
        follow_path.is_modifier = True

        geometry = tree.inputs.geometry("Geometry")
        curve_object = tree.inputs.object("Object")
        factor = tree.inputs.float(
            "Factor", 0.0, min_value=0.0, max_value=1.0, subtype="FACTOR"
        )
        output = tree.outputs.geometry("Geometry")

        object_info = g.ObjectInfo(
            object=curve_object, as_instance=False, transform_space="RELATIVE"
        )
        sample_curve = g.SampleCurve.factor.float(
            curves=object_info.o.geometry,
            factor=factor,
            use_all_curves=False,
        )
        transformed = g.TransformGeometry(
            geometry=geometry,
            mode="Components",
            translation=sample_curve.o.position,
            rotation=(0.0, 0.0, 0.0),
            scale=(1.0, 1.0, 1.0),
        )
        in_bounds = g.BooleanMath.l_and(
            g.Compare.float.greater_than(factor, 0.0010000000474974513),
            g.Compare.float.less_than(factor, 0.9990000128746033),
        )
        switched = g.Switch.geometry(switch=in_bounds, true=transformed)
        g.SetPosition(switched, offset=(0.0, 0.0, 0.05)) >> output

    return follow_path


def visibility_node_group():
    """Create a Geometry Nodes group that controls object visibility."""
    with g.tree("Visibility", arrange="sugiyama") as tree:
        visibility = tree.tree
        visibility.color_tag = "NONE"
        visibility.description = ""
        visibility.default_group_node_width = 140
        visibility.is_modifier = True

        geometry = tree.inputs.geometry("Geometry")
        is_visible = tree.inputs.boolean("Visibility", False)
        output = tree.outputs.geometry("Geometry")
        g.Switch.geometry(switch=is_visible, true=geometry) >> output

        tree.node_positions = {
            "Group Input": (-234, -30),
            "Group Output": (139, 24),
            "Switch": (-34, 33),
        }

    return visibility
