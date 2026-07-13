import bpy, mathutils

# auto generated node group with https://extensions.blender.org/add-ons/node-to-python/


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


def create_grease_pencil_stroke_radius_node_group():
    """Create the shared Blender 5.2 node group for Typst GP outlines.

    Curve-to-Grease-Pencil conversion stores stroke visibility in the
    curve-domain ``hide_stroke`` attribute and thickness in the point-domain
    ``radius`` attribute. The modifier makes the converted strokes visible and
    exposes their radius without changing the fill grouping.
    """
    for existing in bpy.data.node_groups:
        if (
            existing.get(_GREASE_PENCIL_STROKE_NODE_GROUP_MARKER_KEY)
            == _GREASE_PENCIL_STROKE_NODE_GROUP_MARKER
            and existing.bl_idname == "GeometryNodeTree"
            and _interface_input(existing, "Stroke Radius") is not None
        ):
            return existing

    node_group = bpy.data.node_groups.new(
        type="GeometryNodeTree",
        name=GREASE_PENCIL_STROKE_NODE_GROUP,
    )
    node_group.is_modifier = True
    node_group.description = (
        "Show Typst Grease Pencil strokes and control their radius"
    )
    node_group[_GREASE_PENCIL_STROKE_NODE_GROUP_MARKER_KEY] = (
        _GREASE_PENCIL_STROKE_NODE_GROUP_MARKER
    )

    geometry_output = node_group.interface.new_socket(
        name="Geometry",
        in_out="OUTPUT",
        socket_type="NodeSocketGeometry",
    )
    geometry_output.attribute_domain = "POINT"

    geometry_input = node_group.interface.new_socket(
        name="Geometry",
        in_out="INPUT",
        socket_type="NodeSocketGeometry",
    )
    geometry_input.attribute_domain = "POINT"

    radius_input = node_group.interface.new_socket(
        name="Stroke Radius",
        in_out="INPUT",
        socket_type="NodeSocketFloat",
    )
    radius_input.default_value = DEFAULT_GREASE_PENCIL_STROKE_RADIUS
    radius_input.min_value = 0.0
    radius_input.max_value = 10.0
    radius_input.subtype = "DISTANCE"
    radius_input.attribute_domain = "POINT"
    radius_input.description = "Radius of the visible Grease Pencil stroke"

    group_input = node_group.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"
    group_input.location = (-500.0, 0.0)

    show_stroke = node_group.nodes.new("GeometryNodeStoreNamedAttribute")
    show_stroke.name = "Show Stroke"
    show_stroke.label = "Show Stroke"
    show_stroke.data_type = "BOOLEAN"
    show_stroke.domain = "CURVE"
    show_stroke.inputs["Selection"].default_value = True
    show_stroke.inputs["Name"].default_value = "hide_stroke"
    show_stroke.inputs["Value"].default_value = False
    show_stroke.location = (-260.0, 0.0)

    set_radius = node_group.nodes.new("GeometryNodeSetCurveRadius")
    set_radius.name = "Set Stroke Radius"
    set_radius.label = "Set Stroke Radius"
    set_radius.inputs["Selection"].default_value = True
    set_radius.location = (20.0, 0.0)

    group_output = node_group.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True
    group_output.location = (280.0, 0.0)

    node_group.links.new(
        group_input.outputs["Geometry"],
        show_stroke.inputs["Geometry"],
    )
    node_group.links.new(
        show_stroke.outputs["Geometry"],
        set_radius.inputs["Curve"],
    )
    node_group.links.new(
        group_input.outputs["Stroke Radius"],
        set_radius.inputs["Radius"],
    )
    node_group.links.new(
        set_radius.outputs["Curve"],
        group_output.inputs["Geometry"],
    )

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
    radius_socket = _interface_input(node_group, "Stroke Radius")
    modifier = obj.modifiers.new(
        name=GREASE_PENCIL_STROKE_NODE_GROUP,
        type="NODES",
    )
    modifier.node_group = node_group

    # Blender 5.2 exposes modifier inputs through a typed RNA interface. The
    # legacy modifier["Socket_2"] ID-property access is unsupported by the
    # current API.
    modifier_input = getattr(
        modifier.properties.inputs,
        radius_socket.identifier,
    )
    modifier_input.type = "VALUE"
    modifier_input.value = float(stroke_radius)
    return modifier


def create_follow_curve_node_group():
    """
    Creates a Geometry Nodes group that makes an object follow a curve.

    Returns:
        The created node group
    """
    # Create a new node group or use existing one
    follow_path = bpy.data.node_groups.new(type="GeometryNodeTree", name="Follow Path")

    follow_path.color_tag = "NONE"
    follow_path.description = ""
    follow_path.default_group_node_width = 140
    follow_path.is_modifier = True

    # Create interface sockets
    geometry_socket = follow_path.interface.new_socket(
        name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
    )
    geometry_socket.attribute_domain = "POINT"

    geometry_socket_1 = follow_path.interface.new_socket(
        name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
    )
    geometry_socket_1.attribute_domain = "POINT"

    object_socket = follow_path.interface.new_socket(
        name="Object", in_out="INPUT", socket_type="NodeSocketObject"
    )
    object_socket.attribute_domain = "POINT"

    factor_socket = follow_path.interface.new_socket(
        name="Factor", in_out="INPUT", socket_type="NodeSocketFloat"
    )
    factor_socket.default_value = 0.0
    factor_socket.min_value = 0.0
    factor_socket.max_value = 1.0
    factor_socket.subtype = "FACTOR"
    factor_socket.attribute_domain = "POINT"

    # Create nodes
    group_input = follow_path.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"

    group_output = follow_path.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True

    object_info = follow_path.nodes.new("GeometryNodeObjectInfo")
    object_info.name = "Object Info"
    object_info.transform_space = "RELATIVE"
    object_info.inputs[1].default_value = False  # As Instance

    sample_curve = follow_path.nodes.new("GeometryNodeSampleCurve")
    sample_curve.name = "Sample Curve"
    sample_curve.data_type = "FLOAT"
    sample_curve.mode = "FACTOR"
    sample_curve.use_all_curves = False
    sample_curve.inputs[1].default_value = 0.0  # Value
    sample_curve.inputs[4].default_value = 0  # Curve Index

    transform_geometry = follow_path.nodes.new("GeometryNodeTransform")
    transform_geometry.name = "Transform Geometry"
    if bpy.app.version >= (5, 0, 0):
        transform_geometry.inputs[1].default_value = 'Components'
    else:
        transform_geometry.mode = "COMPONENTS"
    transform_geometry.inputs[2].default_value = (0.0, 0.0, 0.0)  # Rotation
    transform_geometry.inputs[3].default_value = (1.0, 1.0, 1.0)  # Scale

    reroute_001 = follow_path.nodes.new("NodeReroute")
    reroute_001.name = "Reroute.001"
    reroute_001.socket_idname = "NodeSocketFloatFactor"
    
    # Add new nodes for boundary checking
    switch = follow_path.nodes.new("GeometryNodeSwitch")
    switch.name = "Switch"
    switch.input_type = "GEOMETRY"

    compare = follow_path.nodes.new("FunctionNodeCompare")
    compare.name = "Compare"
    compare.data_type = "FLOAT"
    compare.mode = "ELEMENT"
    compare.operation = "GREATER_THAN"
    compare.inputs[1].default_value = 0.0010000000474974513  # B

    compare_001 = follow_path.nodes.new("FunctionNodeCompare")
    compare_001.name = "Compare.001"
    compare_001.data_type = "FLOAT"
    compare_001.mode = "ELEMENT"
    compare_001.operation = "LESS_THAN"
    compare_001.inputs[1].default_value = 0.9990000128746033  # B

    boolean_math = follow_path.nodes.new("FunctionNodeBooleanMath")
    boolean_math.name = "Boolean Math"
    boolean_math.operation = "AND"

    reroute = follow_path.nodes.new("NodeReroute")
    reroute.name = "Reroute"
    reroute.socket_idname = "NodeSocketFloatFactor"
    
    # Add Set Position node to slightly adjust Z position
    set_position = follow_path.nodes.new("GeometryNodeSetPosition")
    set_position.name = "Set Position"
    set_position.inputs[1].default_value = True  # Selection
    set_position.inputs[2].default_value = (0.0, 0.0, 0.0)  # Position
    set_position.inputs[3].default_value = (0.0, 0.0, 0.05)  # Offset

    # Set node locations
    group_input.location = (-467.30731201171875, 60.86485290527344)
    group_output.location = (540.0, 180.0)
    object_info.location = (-267.30731201171875, 0.8648511171340942)
    sample_curve.location = (-107.30732727050781, 0.8648511171340942)
    transform_geometry.location = (52.69267272949219, 100.86485290527344)
    reroute_001.location = (-267.30731201171875, -239.13514709472656)
    switch.location = (212.6926727294922, 200.86485290527344)
    compare.location = (-267.30731201171875, 360.8648376464844)
    compare_001.location = (-267.30731201171875, 200.86485290527344)
    boolean_math.location = (-67.30732727050781, 340.8648376464844)
    reroute.location = (-307.30731201171875, 180.86485290527344)
    set_position.location = (380.0, 200.0)

    # Set node dimensions
    group_input.width, group_input.height = 140.0, 100.0
    group_output.width, group_output.height = 140.0, 100.0
    object_info.width, object_info.height = 140.0, 100.0
    sample_curve.width, sample_curve.height = 140.0, 100.0
    transform_geometry.width, transform_geometry.height = 140.0, 100.0
    reroute_001.width, reroute_001.height = 20.0, 100.0
    switch.width, switch.height = 140.0, 100.0
    compare.width, compare.height = 140.0, 100.0
    compare_001.width, compare_001.height = 140.0, 100.0
    boolean_math.width, boolean_math.height = 140.0, 100.0
    reroute.width, reroute.height = 20.0, 100.0
    set_position.width, set_position.height = 140.0, 100.0

    # Create links
    links = follow_path.links
    links.new(
        object_info.outputs[4], sample_curve.inputs[0]
    )  # Object Info.Geometry -> Sample Curve.Curves
    links.new(
        sample_curve.outputs[1], transform_geometry.inputs[1]
    )  # Sample Curve.Position -> Transform Geometry.Translation
    links.new(
        group_input.outputs[0], transform_geometry.inputs[0]
    )  # Group Input.Geometry -> Transform Geometry.Geometry
    links.new(
        set_position.outputs[0], group_output.inputs[0]
    )  # Set Position.Geometry -> Group Output.Geometry
    links.new(
        reroute_001.outputs[0], sample_curve.inputs[2]
    )  # Reroute.001.Output -> Sample Curve.Factor
    links.new(
        group_input.outputs[1], object_info.inputs[0]
    )  # Group Input.Object -> Object Info.Object
    links.new(
        group_input.outputs[2], reroute_001.inputs[0]
    )  # Group Input.Factor -> Reroute.001.Input
    links.new(
        transform_geometry.outputs[0], switch.inputs[2]
    )  # Transform Geometry.Geometry -> Switch.True
    links.new(
        compare.outputs[0], boolean_math.inputs[0]
    )  # Compare.Result -> Boolean Math.Boolean
    links.new(
        compare_001.outputs[0], boolean_math.inputs[1]
    )  # Compare.001.Result -> Boolean Math.Boolean
    links.new(
        boolean_math.outputs[0], switch.inputs[0]
    )  # Boolean Math.Boolean -> Switch.Switch
    links.new(
        reroute.outputs[0], compare.inputs[0]
    )  # Reroute.Output -> Compare.A
    links.new(
        reroute.outputs[0], compare_001.inputs[0]
    )  # Reroute.Output -> Compare.001.A
    links.new(
        group_input.outputs[2], reroute.inputs[0]
    )  # Group Input.Factor -> Reroute.Input
    links.new(
        switch.outputs[0], set_position.inputs[0]
    )  # Switch.Output -> Set Position.Geometry

    return follow_path


#initialize visibility node group
def visibility_node_group():
    """
    Creates a Geometry Nodes group that controls object visibility.
    
    Returns:
        The created node group
    """
    visibility = bpy.data.node_groups.new(type='GeometryNodeTree', name="Visibility")

    visibility.color_tag = 'NONE'
    visibility.description = ""
    visibility.default_group_node_width = 140
    visibility.is_modifier = True

    #visibility interface
    #Socket Geometry
    geometry_socket = visibility.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    geometry_socket.attribute_domain = 'POINT'

    #Socket Geometry
    geometry_socket_1 = visibility.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    geometry_socket_1.attribute_domain = 'POINT'

    #Socket Visibility
    visibility_socket = visibility.interface.new_socket(name="Visibility", in_out='INPUT', socket_type='NodeSocketBool')
    visibility_socket.default_value = False
    visibility_socket.attribute_domain = 'POINT'

    #initialize visibility nodes
    #node Group Input
    group_input = visibility.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"

    #node Group Output
    group_output = visibility.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True

    #node Switch
    switch = visibility.nodes.new("GeometryNodeSwitch")
    switch.name = "Switch"
    switch.input_type = 'GEOMETRY'

    #Set locations
    group_input.location = (-234, -30)
    group_output.location = (139, 24)
    switch.location = (-34, 33)

    #Set dimensions
    group_input.width, group_input.height = 140, 100
    group_output.width, group_output.height = 140, 100
    switch.width, switch.height = 140, 100

    #initialize visibility links
    #switch.Output -> group_output.Geometry
    visibility.links.new(switch.outputs[0], group_output.inputs[0])
    #group_input.Geometry -> switch.True
    visibility.links.new(group_input.outputs[0], switch.inputs[2])
    #group_input.Visibility -> switch.Switch
    visibility.links.new(group_input.outputs[1], switch.inputs[0])
    return visibility
