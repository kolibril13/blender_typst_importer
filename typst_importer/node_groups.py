import bpy, mathutils


# auto generated node group with https://extensions.blender.org/add-ons/node-to-python/

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
    transform_geometry.mode = "COMPONENTS"
    transform_geometry.inputs[2].default_value = (0.0, 0.0, 0.0)  # Rotation
    transform_geometry.inputs[3].default_value = (1.0, 1.0, 1.0)  # Scale

    reroute_001 = follow_path.nodes.new("NodeReroute")
    reroute_001.name = "Reroute.001"
    reroute_001.socket_idname = "NodeSocketFloatFactor"

    # Set node locations
    group_input.location = (-380.0, 60.0)
    group_output.location = (300.0, 60.0)
    object_info.location = (-180.0, 0.0)
    sample_curve.location = (-20.0, 0.0)
    transform_geometry.location = (140.0, 100.0)
    reroute_001.location = (-180.0, -240.0)

    # Set node dimensions
    group_input.width, group_input.height = 140.0, 100.0
    group_output.width, group_output.height = 140.0, 100.0
    object_info.width, object_info.height = 140.0, 100.0
    sample_curve.width, sample_curve.height = 140.0, 100.0
    transform_geometry.width, transform_geometry.height = 140.0, 100.0
    reroute_001.width, reroute_001.height = 16.0, 100.0

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
        transform_geometry.outputs[0], group_output.inputs[0]
    )  # Transform Geometry.Geometry -> Group Output.Geometry
    links.new(
        reroute_001.outputs[0], sample_curve.inputs[2]
    )  # Reroute.001.Output -> Sample Curve.Factor
    links.new(
        group_input.outputs[1], object_info.inputs[0]
    )  # Group Input.Object -> Object Info.Object
    links.new(
        group_input.outputs[2], reroute_001.inputs[0]
    )  # Group Input.Factor -> Reroute.001.Input

    return follow_path
