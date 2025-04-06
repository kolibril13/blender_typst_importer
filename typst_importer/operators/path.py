import bpy
from ..node_groups import create_follow_curve_node_group
from .op_utils import get_or_create_collection

# Helper functions
def create_bezier_curve(first_co, second_co, curve_height):
    """
    Creates a bezier curve between two points in the XY plane.

    Args:
        first_co: The coordinates of the first point
        second_co: The coordinates of the second point
        curve_height: The height parameter that controls the arc's curvature

    Returns:
        The created curve object
    """
    curve_data = bpy.data.curves.new("BezierCurve", type="CURVE")
    curve_data.dimensions = "3D"

    spline = curve_data.splines.new("BEZIER")
    spline.bezier_points.add(1)

    spline.bezier_points[0].co = (first_co.x, first_co.y, first_co.z)
    spline.bezier_points[1].co = (second_co.x, second_co.y, first_co.z)

    # Invert the curve height for correct arc direction
    y = -curve_height

    # Calculate midpoint for handle positioning
    mid_x = (first_co.x + second_co.x) / 2
    mid_y = (first_co.y + second_co.y) / 2

    # Calculate handle offset based on curve height
    dx = second_co.x - first_co.x
    dy = second_co.y - first_co.y

    # Create perpendicular vector for handle offset
    handle_offset_x = -dy * y
    handle_offset_y = dx * y

    spline.bezier_points[0].handle_left_type = "FREE"
    spline.bezier_points[0].handle_right_type = "FREE"
    spline.bezier_points[0].handle_left = (first_co.x, first_co.y, first_co.z)
    spline.bezier_points[0].handle_right = (
        mid_x + handle_offset_x,
        mid_y + handle_offset_y,
        first_co.z,
    )

    spline.bezier_points[1].handle_left_type = "FREE"
    spline.bezier_points[1].handle_right_type = "FREE"
    spline.bezier_points[1].handle_left = (
        mid_x + handle_offset_x,
        mid_y + handle_offset_y,
        first_co.z,
    )
    spline.bezier_points[1].handle_right = (second_co.x, second_co.y, first_co.z)

    curve_obj = bpy.data.objects.new("BezierCurveObject", curve_data)

    return curve_obj


def get_two_selected_objects(context, report_func=None):
    """
    Gets two selected objects, ensuring the second one is the active object.

    Args:
        context: The current Blender context
        report_func: Optional function to report warnings

    Returns:
        Tuple of (first_obj, second_obj) or (None, None) if selection is invalid
    """
    if len(context.selected_objects) != 2:
        if report_func:
            report_func({"WARNING"}, "Select exactly two objects")
        return None, None

    # Unpack the two objects
    first_obj, second_obj = context.selected_objects

    # Ensure `second_obj` is the *active* object
    if second_obj != context.active_object:
        first_obj, second_obj = second_obj, first_obj

    return first_obj, second_obj


class OBJECT_OT_create_arc(bpy.types.Operator):
    """
    Creates an arc in the XY plane.

    Usage:
    1. Select two objects
    2. Run the operator to create an arc between them in the XY plane
    """

    bl_idname = "object.create_arc_xy"
    bl_label = "Create Arc (XY)"
    bl_options = {"REGISTER", "UNDO"}

    curve_height: bpy.props.FloatProperty(
        name="Curve Height",
        description="Adjustable Y parameter that controls the arc's curvature",
        default=1.9,
        min=-10.0,
        max=10.0,
    )

    def execute(self, context):
        first_obj, second_obj = get_two_selected_objects(context, self.report)
        if first_obj is None:
            return {"CANCELLED"}

        first_co = first_obj.location.copy()
        second_co = second_obj.location.copy()

        curve_obj = create_bezier_curve(first_co, second_co, self.curve_height)

        # Check if 'beziers' collection exists, if not create it
        beziers_collection = bpy.data.collections.get("beziers")
        if not beziers_collection:
            beziers_collection = bpy.data.collections.new("beziers")
            context.scene.collection.children.link(beziers_collection)

        # Add the curve to the beziers collection
        beziers_collection.objects.link(curve_obj)

        context.view_layer.objects.active = curve_obj
        curve_obj.select_set(True)

        return {"FINISHED"}


class OBJECT_OT_follow_path(bpy.types.Operator):
    """
    Adds a Geometry Nodes modifier to the selected object, making it follow the active curve.

    Usage:
    1. First select the object you want to follow the path
    2. Then select the curve (path) object last (making it active)
    3. Run the operator to make the object follow the selected curve
    """

    bl_idname = "object.follow_path_constraint"
    bl_label = "Follow Path"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.area is not None
            and context.area.type == "VIEW_3D"
            and context.active_object is not None
            and len(context.selected_objects) >= 2
        )

    def execute(self, context):
        # Get the two selected objects
        follower_obj, curve_obj = get_two_selected_objects(context, self.report)

        if follower_obj is None or curve_obj is None:
            return {"CANCELLED"}

        if curve_obj.type != "CURVE":
            self.report({"WARNING"}, "Active object must be a curve")
            return {"CANCELLED"}

        # Get or create the AnimationObjs collection
        target_collection = get_or_create_collection("AnimationObjs")

        # Create a copy of the follower obj
        bpy.ops.object.select_all(action="DESELECT")
        follower_obj.select_set(True)
        bpy.context.view_layer.objects.active = follower_obj
        bpy.ops.object.duplicate()
        burst_obj = bpy.context.active_object
        arise_obj = follower_obj

        # Ensure the copy has a descriptive name
        arise_obj.name = f"{follower_obj.name}_arise"
        burst_obj.name = f"{follower_obj.name}_burst"

        # Move the burst object to the AnimationObjs collection
        # First remove from current collections
        for collection in bpy.data.collections:
            if burst_obj.name in collection.objects:
                collection.objects.unlink(burst_obj)
        
        # Add to target collection
        target_collection.objects.link(burst_obj)

        # Create a geometry nodes modifier for the moving obj (for path following)
        burst_obj_modifier = burst_obj.modifiers.new(name="FollowPath", type="NODES")

        # Always create a new geometry nodes group to avoid conflicts
        geometry_nodes = create_follow_curve_node_group()

        # Assign the node group to the modifier
        burst_obj_modifier.node_group = geometry_nodes

        # Set the curve obj as the target
        burst_obj_modifier["Socket_2"] = curve_obj

        # Get the current frame
        current_frame = context.scene.frame_current

        # Clear any existing keyframes for this property
        if burst_obj.animation_data and burst_obj.animation_data.action:
            fcurves = burst_obj.animation_data.action.fcurves
            for fc in fcurves:
                if fc.data_path == 'modifiers["FollowPath"]["Socket_3"]':
                    burst_obj.animation_data.action.fcurves.remove(fc)
                    break

        # Add keyframe at current frame with factor 0.0
        burst_obj_modifier["Socket_3"] = 0.0
        burst_obj.keyframe_insert(
            'modifiers["FollowPath"]["Socket_3"]', frame=current_frame
        )

        # Add keyframe 10 frames later with factor 1.0
        next_frame = current_frame + 10
        burst_obj_modifier["Socket_3"] = 1.0
        burst_obj.keyframe_insert(
            'modifiers["FollowPath"]["Socket_3"]', frame=next_frame
        )

        # Reset to initial value for display
        burst_obj_modifier["Socket_3"] = 0.0

        # Toggle visibility of the standing object
        from ..operators.visibility import toggle_visibility
        toggle_visibility(arise_obj, current_frame, make_visible=False)

        self.report(
            {"INFO"},
            f"Created objects: {arise_obj.name} (with Visibility modifier) and {burst_obj.name} (with Follow Path modifier) in 'AnimationObjs' collection",
        )
        return {"FINISHED"}


class OBJECT_OT_arc_and_follow(bpy.types.Operator):
    """
    Creates an arc between two objects and sets up the first object to follow the path.

    Usage:
    1. Select two objects
    2. Run the operator to create an arc and make the first object follow it
    """

    bl_idname = "object.arc_and_follow"
    bl_label = "Arc and Follow"
    bl_options = {"REGISTER", "UNDO"}

    curve_height: bpy.props.FloatProperty(
        name="Curve Height",
        description="Adjustable Y parameter that controls the arc's curvature",
        default=1.9,
        min=-10.0,
        max=10.0,
    )

    def execute(self, context):
        # Step 1: Get the two selected objects
        first_obj, second_obj = get_two_selected_objects(context, self.report)
        if first_obj is None:
            return {"CANCELLED"}

        # Step 2: Create an arc between them
        first_co = first_obj.location.copy()
        second_co = second_obj.location.copy()

        curve_obj = create_bezier_curve(first_co, second_co, self.curve_height)

        # Check if 'beziers' collection exists, if not create it
        beziers_collection = bpy.data.collections.get("beziers")
        if not beziers_collection:
            beziers_collection = bpy.data.collections.new("beziers")
            context.scene.collection.children.link(beziers_collection)

        # Add the curve to the beziers collection
        beziers_collection.objects.link(curve_obj)

        # Get or create the AnimationObjs collection
        target_collection = get_or_create_collection("AnimationObjs")

        # Step 3: Set up the first object to follow the path
        # Create a copy of the first object
        bpy.ops.object.select_all(action="DESELECT")
        first_obj.select_set(True)
        bpy.context.view_layer.objects.active = first_obj
        bpy.ops.object.duplicate()
        arise_obj = first_obj
        burst_obj = bpy.context.active_object

        # Create a common prefix for all related objects
        prefix = f"{first_obj.name}"

        # Ensure the copy has a descriptive name
        arise_obj.name = f"{prefix}_arise"
        burst_obj.name = f"{prefix}_burst"

        # Move the burst object to the AnimationObjs collection
        # First remove from current collections
        for collection in bpy.data.collections:
            if burst_obj.name in collection.objects:
                collection.objects.unlink(burst_obj)
        
        # Add to target collection
        target_collection.objects.link(burst_obj)

        # Create a copy of the second object at z=0
        bpy.ops.object.select_all(action="DESELECT")
        second_obj.select_set(True)
        bpy.context.view_layer.objects.active = second_obj
        bpy.ops.object.duplicate()
        conclude_obj = bpy.context.active_object
        conclude_obj.name = f"{prefix}_conclude"

        # Place the destination object at z=0
        conclude_obj.location.z = 0

        # Move the conclude object to the AnimationObjs collection
        # First remove from current collections
        for collection in bpy.data.collections:
            if conclude_obj.name in collection.objects:
                collection.objects.unlink(conclude_obj)
        
        # Add to target collection
        target_collection.objects.link(conclude_obj)

        # Create a geometry nodes modifier for the moving obj (for path following)
        burst_obj_modifier = burst_obj.modifiers.new(name="FollowPath", type="NODES")

        # Always create a new geometry nodes group to avoid conflicts
        geometry_nodes = create_follow_curve_node_group()

        # Assign the node group to the modifier
        burst_obj_modifier.node_group = geometry_nodes

        # Set the curve obj as the target
        burst_obj_modifier["Socket_2"] = curve_obj

        # Get the current frame
        current_frame = context.scene.frame_current

        # Clear any existing keyframes for this property
        if burst_obj.animation_data and burst_obj.animation_data.action:
            fcurves = burst_obj.animation_data.action.fcurves
            for fc in fcurves:
                if fc.data_path == 'modifiers["FollowPath"]["Socket_3"]':
                    burst_obj.animation_data.action.fcurves.remove(fc)
                    break

        # Add keyframe at current frame with factor 0.0
        burst_obj_modifier["Socket_3"] = 0.0
        burst_obj.keyframe_insert(
            'modifiers["FollowPath"]["Socket_3"]', frame=current_frame
        )

        # Add keyframe 10 frames later with factor 1.0
        next_frame = current_frame + 10
        burst_obj_modifier["Socket_3"] = 1.0
        burst_obj.keyframe_insert(
            'modifiers["FollowPath"]["Socket_3"]', frame=next_frame
        )

        # Reset to initial value for display
        burst_obj_modifier["Socket_3"] = 0.0

        # Step 4: Toggle visibility of the standing object
        from ..operators.visibility import toggle_visibility
        toggle_visibility(arise_obj, current_frame, make_visible=False)

        # Step 5: Set up visibility for the destination object

        # Make the destination object visible at the end of the animation
        toggle_visibility(conclude_obj, next_frame - 1, make_visible=True)

        self.report(
            {"INFO"},
            f"Created arc and set up {burst_obj.name} and {conclude_obj.name} in 'AnimationObjs' collection. {arise_obj.name} will be hidden.",
        )
        return {"FINISHED"}


class OBJECT_OT_hide_bezier_collection(bpy.types.Operator):
    """Hide all objects in the 'beziers' collection"""

    bl_idname = "object.hide_bezier_collection"
    bl_label = "Hide Bezier Collection"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        hidden_count = 0

        # Find the "beziers" collection
        bezier_collection = None
        for collection in bpy.data.collections:
            if collection.name.lower() == "beziers":
                bezier_collection = collection
                break

        if bezier_collection:
            # Hide all objects in the bezier collection
            for obj in bezier_collection.objects:
                obj.hide_viewport = True
                hidden_count += 1

            self.report(
                {"INFO"}, f"Hidden {hidden_count} objects from 'beziers' collection"
            )
        else:
            self.report({"WARNING"}, "Collection 'beziers' not found")

        return {"FINISHED"} 