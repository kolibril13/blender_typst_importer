import bpy

def create_follow_curve_node_group():
    """
    Creates a Geometry Nodes group that makes an object follow a curve.
    
    Returns:
        The created node group
    """
    # Create a new node group or use existing one
    geometry_nodes = bpy.data.node_groups.new(
        type="GeometryNodeTree", name="Follow Path"
    )

    geometry_nodes.color_tag = "NONE"
    geometry_nodes.description = ""
    geometry_nodes.default_group_node_width = 140
    geometry_nodes.is_modifier = True

    # Create interface sockets
    geometry_socket = geometry_nodes.interface.new_socket(
        name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
    )
    geometry_socket.attribute_domain = "POINT"

    geometry_socket_1 = geometry_nodes.interface.new_socket(
        name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
    )
    geometry_socket_1.attribute_domain = "POINT"

    object_socket = geometry_nodes.interface.new_socket(
        name="Object", in_out="INPUT", socket_type="NodeSocketObject"
    )
    object_socket.attribute_domain = "POINT"

    factor_socket = geometry_nodes.interface.new_socket(
        name="Factor", in_out="INPUT", socket_type="NodeSocketFloat"
    )
    factor_socket.default_value = 0.0
    factor_socket.min_value = 0.0
    factor_socket.max_value = 1.0
    factor_socket.subtype = "FACTOR"
    factor_socket.attribute_domain = "POINT"

    # Create nodes
    group_input = geometry_nodes.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"

    group_output = geometry_nodes.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True

    object_info = geometry_nodes.nodes.new("GeometryNodeObjectInfo")
    object_info.name = "Object Info"
    object_info.transform_space = "RELATIVE"
    object_info.inputs[1].default_value = False  # As Instance

    sample_curve = geometry_nodes.nodes.new("GeometryNodeSampleCurve")
    sample_curve.name = "Sample Curve"
    sample_curve.data_type = "FLOAT"
    sample_curve.mode = "FACTOR"
    sample_curve.use_all_curves = False
    sample_curve.inputs[1].default_value = 0.0  # Value
    sample_curve.inputs[4].default_value = 0  # Curve Index

    transform_geometry = geometry_nodes.nodes.new("GeometryNodeTransform")
    transform_geometry.name = "Transform Geometry"
    transform_geometry.mode = "COMPONENTS"
    transform_geometry.inputs[2].default_value = (0.0, 0.0, 0.0)  # Rotation
    transform_geometry.inputs[3].default_value = (1.0, 1.0, 1.0)  # Scale

    # Set node locations
    group_input.location = (-823.972, -15.397)
    group_output.location = (453.286, 0.0)
    object_info.location = (-150.870, -76.182)
    sample_curve.location = (63.414, -107.258)
    transform_geometry.location = (251.888, 36.368)

    # Set node dimensions
    for node in [group_input, group_output, object_info, sample_curve, transform_geometry]:
        node.width = 140.0
        node.height = 100.0

    # Create links
    links = geometry_nodes.links
    links.new(group_input.outputs[1], object_info.inputs[0])  # Object
    links.new(object_info.outputs[4], sample_curve.inputs[0])  # Geometry -> Curves
    links.new(sample_curve.outputs[1], transform_geometry.inputs[1])  # Position -> Translation
    links.new(group_input.outputs[0], transform_geometry.inputs[0])  # Geometry
    links.new(transform_geometry.outputs[0], group_output.inputs[0])  # Final Geometry
    links.new(group_input.outputs[2], sample_curve.inputs[2])  # Factor

    return geometry_nodes 