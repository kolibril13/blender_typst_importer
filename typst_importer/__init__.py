from .utils import add_current_module_to_path
import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from pathlib import Path
import time
from .node_groups import create_follow_curve_node_group, visibility_node_group


# Import the helper function from typst_to_svg.py
from .typst_to_svg import typst_to_blender_curves


# Operator for the button and drag-and-drop
class ImportTypstOperator(bpy.types.Operator, ImportHelper):
    """Operator to import a .txt or .typ file, compile it via Typst, and import as SVG in Blender."""

    bl_idname = "import_scene.import_txt_typst"
    bl_label = "Import Typst File (.txt/.typ)"
    bl_options = {"PRESET", "UNDO"}

    # ImportHelper provides a default 'filepath' property,
    # but we redefine it here with SKIP_SAVE to support drag–n–drop.
    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})

    # Set a default extension (the user can change it in the file browser)
    filename_ext = ".txt"
    filter_glob: StringProperty(default="*.txt;*.typ", options={"HIDDEN"}, maxlen=255)

    def execute(self, context):
        # Verify that the selected file is either a .txt or .typ file.
        if not self.filepath.lower().endswith((".txt", ".typ")):
            self.report({"WARNING"}, "Selected file is not a TXT or TYP file")
            return {"CANCELLED"}

        # Prepare file variables
        typst_file = Path(self.filepath)
        file_name_without_ext = typst_file.stem

        # Start the timer
        start_time = time.perf_counter()

        # Compile and import the file using our helper function
        collection = typst_to_blender_curves(typst_file)

        elapsed_time_ms = (time.perf_counter() - start_time) * 1000
        self.report(
            {"INFO"},
            f" 🦢  Typst Importer: {typst_file.name} rendered in {elapsed_time_ms:.2f} ms as {collection.name}",
        )
        return {"FINISHED"}

    def invoke(self, context, event):
        # If the operator was invoked with a filepath (drag–n–drop), execute directly.
        if self.filepath:
            return self.execute(context)
        # Otherwise, open the file browser.
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


# File Handler for drag-and-drop support
class TXT_FH_import(bpy.types.FileHandler):
    """A file handler to allow .txt and .typ files to be dragged and dropped directly into Blender."""

    bl_idname = "TXT_FH_import"
    bl_label = "File handler for TXT/TYP import (Typst)"
    bl_import_operator = "import_scene.import_txt_typst"
    bl_file_extensions = ".txt;.typ"

    @classmethod
    def poll_drop(cls, context):
        # Allow drag–n–drop
        return context.area is not None


# Global list to store our keymap entries for cleanup.
addon_keymaps = []


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


class OBJECT_OT_align_to_active(bpy.types.Operator):
    """
    Aligns selected objects' X and Y coordinates to match the active object's location, while preserving Z coordinates.

    Usage:
    1. Select one or more objects to align
    2. Select the target object last (making it active)
    3. Run the operator to align all selected objects to the active object's XY position
    """

    bl_idname = "object.align_object_xy"
    bl_label = "Align Object (XY)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.area is not None
            and context.area.type == "VIEW_3D"
            and context.active_object is not None
        )

    def execute(self, context):
        active_obj = context.active_object
        target_loc = (
            active_obj.location.copy()
        )  # Copy location to avoid direct reference issues
        for obj in context.selected_objects:
            if obj != active_obj:
                # Only snap X and Y; leave Z unchanged.
                obj.location.x = target_loc.x
                obj.location.y = target_loc.y
        return {"FINISHED"}

class OBJECT_OT_align_collection(bpy.types.Operator):
    """
    Aligns multiple collections of objects by moving them based on the active object's location.

    Usage:
    1. Select objects from different collections to align
    2. Select the target object last (making it active)
    3. Run the operator to move all collections to align with the active object
    """

    bl_idname = "object.align_collection_xy"
    bl_label = "Align Collection (XY)"
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
        # Need at least 2 objects selected
        if len(context.selected_objects) < 2:
            self.report(
                {"WARNING"},
                "Select at least 2 objects: source objects and destination object",
            )
            return {"CANCELLED"}

        # The active object is the destination
        destination = context.active_object
        
        # All other selected objects are sources
        source_objects = [obj for obj in context.selected_objects if obj != destination]
        
        # For each source object, move its entire collection
        for source in source_objects:
            # Compute the translation vector from source to destination
            delta = destination.location - source.location
            
            # Gather all objects in every collection that the source object is a member of,
            # including objects in sub-collections
            objects_to_move = set()
            
            def gather_objects_from_collection(collection):
                # Add objects directly in this collection
                objects_to_move.update(collection.objects)
                # Recursively process sub-collections
                for child_collection in collection.children:
                    gather_objects_from_collection(child_collection)
            
            if source.users_collection:
                for coll in source.users_collection:
                    gather_objects_from_collection(coll)
            else:
                # In case the source isn't in any collection (rare), move just the source
                objects_to_move.add(source)
            
            # Move each object by delta only in the X and Y axes, except for the destination
            for obj in objects_to_move:
                if obj == destination or obj in source_objects and obj != source:
                    continue
                obj.location.x += delta.x
                obj.location.y += delta.y
        
        self.report(
            {"INFO"},
            f"Aligned {len(source_objects)} collections to {destination.name}"
        )
        return {"FINISHED"}


def toggle_visibility(obj, current_frame, make_visible):
    """
    Helper function to toggle visibility of an object using Geometry Nodes modifier.

    Args:
        obj: The object to toggle visibility for
        current_frame: The current frame in the timeline
        make_visible: Boolean indicating whether to make the object visible (True) or invisible (False)

    Returns:
        The visibility modifier
    """
    # Check if the object already has a visibility modifier
    visibility_modifier = None
    for modifier in obj.modifiers:
        if modifier.type == "NODES" and modifier.name == "Visibility":
            visibility_modifier = modifier
            break

    # If no visibility modifier exists, add one
    if not visibility_modifier:
        visibility_modifier = obj.modifiers.new(name="Visibility", type="NODES")
        visibility_modifier.node_group = visibility_node_group()

    # Set initial state at current frame
    initial_state = not make_visible
    visibility_modifier["Socket_2"] = initial_state
    obj.keyframe_insert('modifiers["Visibility"]["Socket_2"]', frame=current_frame)

    # Set target state at next frame
    target_state = make_visible
    visibility_modifier["Socket_2"] = target_state
    obj.keyframe_insert('modifiers["Visibility"]["Socket_2"]', frame=current_frame + 1)

    # Reset to initial state for display
    visibility_modifier["Socket_2"] = initial_state

    return visibility_modifier


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

        # Get the collection of the first object
        first_obj_collection = None
        for collection in bpy.data.collections:
            if follower_obj.name in collection.objects:
                first_obj_collection = collection
                break

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
        toggle_visibility(arise_obj, current_frame, make_visible=False)

        self.report(
            {"INFO"},
            f"Created objects: {arise_obj.name} (with Visibility modifier) and {burst_obj.name} (with Follow Path modifier)",
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

        # Get the collection of the first object
        first_obj_collection = None
        for collection in bpy.data.collections:
            if first_obj.name in collection.objects:
                first_obj_collection = collection
                break

        # Create a copy of the second object at z=0
        bpy.ops.object.select_all(action="DESELECT")
        second_obj.select_set(True)
        bpy.context.view_layer.objects.active = second_obj
        bpy.ops.object.duplicate()
        conclude_obj = bpy.context.active_object
        conclude_obj.name = f"{prefix}_conclude"

        # Place the destination object at z=0
        conclude_obj.location.z = 0

        # Move the destination object to the first object's collection
        if first_obj_collection:
            # Remove from current collection
            for collection in bpy.data.collections:
                if conclude_obj.name in collection.objects:
                    collection.objects.unlink(conclude_obj)
            # Add to first object's collection
            first_obj_collection.objects.link(conclude_obj)

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
        toggle_visibility(arise_obj, current_frame, make_visible=False)

        # Step 5: Set up visibility for the destination object

        # Make the destination object visible at the end of the animation
        toggle_visibility(conclude_obj, next_frame - 1, make_visible=True)

        self.report(
            {"INFO"},
            f"Created arc and set up {burst_obj.name} to follow it. {arise_obj.name} will be hidden. {conclude_obj.name} will appear at the end.",
        )
        return {"FINISHED"}


class OBJECT_OT_visibility_on(bpy.types.Operator):
    """
    Turn on visibility for selected objects
    """

    bl_idname = "object.visibility_on"
    bl_label = "On (Visibility)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.selected_objects

    def execute(self, context):
        # Get the current frame
        current_frame = context.scene.frame_current

        for obj in context.selected_objects:
            toggle_visibility(obj, current_frame, True)

        self.report(
            {"INFO"},
            f"Turned on visibility for {len(context.selected_objects)} objects",
        )
        return {"FINISHED"}


class OBJECT_OT_visibility_off(bpy.types.Operator):
    """
    Turn off visibility for selected objects
    """

    bl_idname = "object.visibility_off"
    bl_label = "Off (Visibility)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.selected_objects

    def execute(self, context):
        # Get the current frame
        current_frame = context.scene.frame_current

        for obj in context.selected_objects:
            toggle_visibility(obj, current_frame, False)

        self.report(
            {"INFO"},
            f"Turned off visibility for {len(context.selected_objects)} objects",
        )
        return {"FINISHED"}


# Fade In operator
class OBJECT_OT_fade_in(bpy.types.Operator):
    """Fade in selected objects"""

    bl_idname = "object.fade_in"
    bl_label = "Fade In Objects"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.selected_objects

    def execute(self, context):
        # Get the current frame
        current_frame = context.scene.frame_current
        end_frame = current_frame + 10

        for obj in context.selected_objects:
            # First make the object visible
            toggle_visibility(obj, current_frame, True)  # Then turn visiblity on

            # Ensure the opacity property exists
            if "opacity" not in obj:
                obj["opacity"] = 0.0

            # Set initial opacity to 0
            obj["opacity"] = 0.0
            obj.keyframe_insert(data_path='["opacity"]', frame=current_frame)

            # Set final opacity to 1
            obj["opacity"] = 1.0
            obj.keyframe_insert(data_path='["opacity"]', frame=end_frame)

            # Reset to initial value for display
            obj["opacity"] = 0.0

        self.report(
            {"INFO"},
            f"Fading in {len(context.selected_objects)} objects over 10 frames",
        )
        return {"FINISHED"}


# Fade In and Move to Animation Plane operator
class OBJECT_OT_fade_in_to_plane(bpy.types.Operator):
    """Fade in selected objects and move copies to the animation plane (first collection)"""

    bl_idname = "object.fade_in_to_plane"
    bl_label = "Fade In (Move to Animation Plane)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.selected_objects

    def execute(self, context):
        # Get the current frame
        current_frame = context.scene.frame_current
        end_frame = current_frame + 10

        # Get the first collection in the scene
        target_collection = None
        if bpy.data.collections:
            target_collection = bpy.data.collections[0]

        if not target_collection:
            self.report({"WARNING"}, "No collections found in the scene")
            return {"CANCELLED"}

        created_objects = []

        for obj in context.selected_objects:
            # Create a copy of the object
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            context.view_layer.objects.active = obj
            bpy.ops.object.duplicate()

            # Get the newly created copy
            copy_obj = context.active_object
            copy_obj.name = f"{obj.name}_animation"

            # Set z coordinate to 0
            copy_obj.location.z = 0

            # Move the copy to the first collection
            # First remove from current collections
            for collection in bpy.data.collections:
                if copy_obj.name in collection.objects:
                    collection.objects.unlink(copy_obj)

            # Add to target collection
            target_collection.objects.link(copy_obj)
            #
            # Make the object visible
            toggle_visibility(copy_obj, current_frame, True)

            # Ensure the opacity property exists
            if "opacity" not in copy_obj:
                copy_obj["opacity"] = 0.0

            # Set initial opacity to 0
            copy_obj["opacity"] = 0.0
            copy_obj.keyframe_insert(data_path='["opacity"]', frame=current_frame)

            # Set final opacity to 1
            copy_obj["opacity"] = 1.0
            copy_obj.keyframe_insert(data_path='["opacity"]', frame=end_frame)

            # Reset to initial value for display
            copy_obj["opacity"] = 0.0

            created_objects.append(copy_obj.name)

        # Select all the newly created objects
        bpy.ops.object.select_all(action="DESELECT")
        for obj_name in created_objects:
            if obj_name in bpy.data.objects:
                bpy.data.objects[obj_name].select_set(True)

        self.report(
            {"INFO"},
            f"Created and fading in {len(created_objects)} objects in collection '{target_collection.name}'",
        )
        return {"FINISHED"}


# Hide Bezier Collection operator
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
                {"INFO"},
                f"Hidden {hidden_count} objects from 'beziers' collection"
            )
        else:
            self.report(
                {"WARNING"},
                "Collection 'beziers' not found"
            )
            
        return {"FINISHED"}


# Fade Out operator
class OBJECT_OT_fade_out(bpy.types.Operator):
    """Fade out selected objects"""

    bl_idname = "object.fade_out"
    bl_label = "Fade Out Objects"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.selected_objects

    def execute(self, context):
        # Get the current frame
        current_frame = context.scene.frame_current
        end_frame = current_frame + 10

        for obj in context.selected_objects:
            # Ensure the opacity property exists
            if "opacity" not in obj:
                obj["opacity"] = 1.0

            # Set initial opacity to 1
            obj["opacity"] = 1.0
            obj.keyframe_insert(data_path='["opacity"]', frame=current_frame)

            # Set final opacity to 0
            obj["opacity"] = 0.0
            obj.keyframe_insert(data_path='["opacity"]', frame=end_frame)

            # After fading out, make the object invisible
            toggle_visibility(obj, end_frame, False)

            # Reset to initial value for display
            obj["opacity"] = 1.0

        self.report(
            {"INFO"},
            f"Fading out {len(context.selected_objects)} objects over 10 frames",
        )
        return {"FINISHED"}


# Panel for the N-panel sidebar
class VIEW3D_PT_typst_animation_tools(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Typst Tools"
    bl_label = "Animation Tools"

    def draw(self, context):
        layout = self.layout

        # Alignment tools
        box = layout.box()
        box.label(text="Alignment")
        box.operator(
            OBJECT_OT_align_to_active.bl_idname,
            text="Align Object (XY)",
            icon="SNAP_NORMAL",
        )
        box.operator(
            OBJECT_OT_align_collection.bl_idname,
            text="Align Collection (XY)",
            icon="GROUP",
        )

        # Arc and path tools
        box = layout.box()
        box.label(text="Path Animation")
        box.operator(
            OBJECT_OT_create_arc.bl_idname, text="Create Arc (XY)", icon="SPHERECURVE"
        )
        box.operator(
            OBJECT_OT_follow_path.bl_idname, text="Follow Path", icon="CURVE_PATH"
        )
        box.operator(
            OBJECT_OT_arc_and_follow.bl_idname,
            text="Arc and Follow",
            icon="FORCE_CURVE",
        )
        box.operator(
            OBJECT_OT_hide_bezier_collection.bl_idname,
            text="Hide Bezier Curves",
            icon="HIDE_ON",
        )

        # Visibility tools
        box = layout.box()
        box.label(text="Visibility")
        row = box.row(align=True)
        row.operator(OBJECT_OT_visibility_on.bl_idname, text="On", icon="HIDE_OFF")
        row.operator(OBJECT_OT_visibility_off.bl_idname, text="Off", icon="HIDE_ON")

        # Fade tools
        box = layout.box()
        box.label(text="Fade Effects")
        box.operator(
            OBJECT_OT_fade_in.bl_idname, text="Fade In Objects", icon="TRIA_RIGHT"
        )
        box.operator(
            OBJECT_OT_fade_in_to_plane.bl_idname,
            text="Fade In (To Animation Plane)",
            icon="TRACKING_FORWARDS",
        )
        box.operator(
            OBJECT_OT_fade_out.bl_idname, text="Fade Out Objects", icon="TRIA_LEFT"
        )


def menu_func_import(self, context):
    """Add an entry into the File > Import menu."""
    self.layout.operator(ImportTypstOperator.bl_idname, text="Typst 🦢 via (.txt/.typ)")


def register():
    # Add the current module to Python's path to ensure imports work correctly
    add_current_module_to_path()

    # Register Blender classes (operators and file handler)
    # 1. XY snapping operator for aligning objects
    bpy.utils.register_class(OBJECT_OT_align_to_active)
    # 2. Group movement operator
    bpy.utils.register_class(OBJECT_OT_align_collection)
    # 3. Arc creation operator
    bpy.utils.register_class(OBJECT_OT_create_arc)
    # 4. Arc and Follow operator
    bpy.utils.register_class(OBJECT_OT_arc_and_follow)
    # 5. Follow path operator
    bpy.utils.register_class(OBJECT_OT_follow_path)
    # 6. Visibility operators
    bpy.utils.register_class(OBJECT_OT_visibility_on)
    bpy.utils.register_class(OBJECT_OT_visibility_off)
    # 7. Fade operators
    bpy.utils.register_class(OBJECT_OT_fade_in)
    bpy.utils.register_class(OBJECT_OT_fade_in_to_plane)
    bpy.utils.register_class(OBJECT_OT_fade_out)
    # 8. Hide bezier curves operator
    bpy.utils.register_class(OBJECT_OT_hide_bezier_collection)
    # 9. Main Typst import operator that handles file selection and import
    bpy.utils.register_class(ImportTypstOperator)
    # 10. File handler for drag-and-drop support of .txt/.typ files
    bpy.utils.register_class(TXT_FH_import)
    # 11. Register the sidebar panel
    bpy.utils.register_class(VIEW3D_PT_typst_animation_tools)

    # Add menu entries
    # 1. Add Typst importer to the File > Import menu
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

    # Set up keyboard shortcuts
    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name="Object Mode", space_type="EMPTY")
    # Bind the 'J' key to trigger the XY snap operator
    kmi = km.keymap_items.new(
        OBJECT_OT_align_to_active.bl_idname, type="J", value="PRESS"
    )
    addon_keymaps.append((km, kmi))
    # Bind the 'L' key to trigger the group movement operator
    kmi = km.keymap_items.new(
        OBJECT_OT_align_collection.bl_idname, type="L", value="PRESS"
    )
    addon_keymaps.append((km, kmi))


def unregister():
    # Clean up keyboard shortcuts
    # Remove all keymaps that were added by the addon
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    # Remove menu entries
    # 1. Remove from File > Import menu
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    # Unregister Blender classes in reverse order
    bpy.utils.unregister_class(VIEW3D_PT_typst_animation_tools)
    bpy.utils.unregister_class(TXT_FH_import)
    bpy.utils.unregister_class(ImportTypstOperator)
    bpy.utils.unregister_class(OBJECT_OT_hide_bezier_collection)
    bpy.utils.unregister_class(OBJECT_OT_fade_out)
    bpy.utils.unregister_class(OBJECT_OT_fade_in_to_plane)
    bpy.utils.unregister_class(OBJECT_OT_fade_in)
    bpy.utils.unregister_class(OBJECT_OT_visibility_off)
    bpy.utils.unregister_class(OBJECT_OT_visibility_on)
    bpy.utils.unregister_class(OBJECT_OT_arc_and_follow)
    bpy.utils.unregister_class(OBJECT_OT_follow_path)
    bpy.utils.unregister_class(OBJECT_OT_create_arc)
    bpy.utils.unregister_class(OBJECT_OT_align_collection)
    bpy.utils.unregister_class(OBJECT_OT_align_to_active)


if __name__ == "__main__":
    register()
