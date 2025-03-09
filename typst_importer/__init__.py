from .utils import add_current_module_to_path
import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from pathlib import Path
import time

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
        context.collection.objects.link(curve_obj)
        context.view_layer.objects.active = curve_obj
        curve_obj.select_set(True)

        return {"FINISHED"}


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
    Aligns a collection of objects by moving them based on the active object's location.

    Usage:
    1. Select one or more objects to align (from collection A)
    2. Select the target object last (making it active, Object B)
    3. Run the operator to move Object A's collection to align with Object B
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
        )

    def execute(self, context):
        # Ensure exactly 2 objects are selected.
        if len(context.selected_objects) != 2:
            self.report(
                {"WARNING"},
                "Select exactly 2 objects: source (Object A) and destination (Object B)",
            )
            return {"CANCELLED"}

        destination = context.active_object  # Object B
        # Determine the source object (Object A) as the other selected object.
        source = next(
            (obj for obj in context.selected_objects if obj != destination), None
        )
        if source is None:
            self.report({"WARNING"}, "Source object could not be determined.")
            return {"CANCELLED"}

        # Compute the translation vector from A to B.
        delta = destination.location - source.location

        # Gather all objects in every collection that Object A is a member of,
        # including objects in sub-collections.
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
            # In case the source isn't in any collection (rare), move just the source.
            objects_to_move.add(source)

        # Move each object by delta only in the X and Y axes, except for the destination.
        for obj in objects_to_move:
            if obj == destination:
                continue
            obj.location.x += delta.x
            obj.location.y += delta.y

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

        # Create a geometry nodes modifier
        modifier = follower_obj.modifiers.new(name="FollowPath", type="NODES")

        # Always create a new geometry nodes group to avoid conflicts
        geometry_nodes = self.create_follow_curve_node_group()

        # Assign the node group to the modifier
        modifier.node_group = geometry_nodes

        # Set the curve object as the target - simpler approach
        modifier["Socket_2"] = curve_obj

        self.report(
            {"INFO"},
            f"Added Follow Path modifier to {follower_obj.name} following {curve_obj.name}",
        )
        return {"FINISHED"}

    def create_follow_curve_node_group(self):
        geometry_nodes = bpy.data.node_groups.new(
            type="GeometryNodeTree", name="Follow Path"
        )

        geometry_nodes.color_tag = "NONE"
        geometry_nodes.description = ""
        geometry_nodes.default_group_node_width = 140

        geometry_nodes.is_modifier = True

        # Geometry nodes interface
        # Socket Geometry
        geometry_socket = geometry_nodes.interface.new_socket(
            name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
        )
        geometry_socket.attribute_domain = "POINT"

        # Socket Geometry
        geometry_socket_1 = geometry_nodes.interface.new_socket(
            name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
        )
        geometry_socket_1.attribute_domain = "POINT"

        # Socket Object
        object_socket = geometry_nodes.interface.new_socket(
            name="Object", in_out="INPUT", socket_type="NodeSocketObject"
        )
        object_socket.attribute_domain = "POINT"

        # Socket Factor
        factor_socket = geometry_nodes.interface.new_socket(
            name="Factor", in_out="INPUT", socket_type="NodeSocketFloat"
        )
        factor_socket.default_value = 0.0
        factor_socket.min_value = 0.0
        factor_socket.max_value = 1.0
        factor_socket.subtype = "FACTOR"
        factor_socket.attribute_domain = "POINT"

        # Initialize geometry_nodes nodes
        # Node Group Input
        group_input = geometry_nodes.nodes.new("NodeGroupInput")
        group_input.name = "Group Input"

        # Node Group Output
        group_output = geometry_nodes.nodes.new("NodeGroupOutput")
        group_output.name = "Group Output"
        group_output.is_active_output = True

        # Node Object Info
        object_info = geometry_nodes.nodes.new("GeometryNodeObjectInfo")
        object_info.name = "Object Info"
        object_info.transform_space = "RELATIVE"
        # As Instance
        object_info.inputs[1].default_value = False

        # Node Sample Curve
        sample_curve = geometry_nodes.nodes.new("GeometryNodeSampleCurve")
        sample_curve.name = "Sample Curve"
        sample_curve.data_type = "FLOAT"
        sample_curve.mode = "FACTOR"
        sample_curve.use_all_curves = False
        # Value
        sample_curve.inputs[1].default_value = 0.0
        # Curve Index
        sample_curve.inputs[4].default_value = 0

        # Node Transform Geometry
        transform_geometry = geometry_nodes.nodes.new("GeometryNodeTransform")
        transform_geometry.name = "Transform Geometry"
        transform_geometry.mode = "COMPONENTS"
        # Rotation
        transform_geometry.inputs[2].default_value = (0.0, 0.0, 0.0)
        # Scale
        transform_geometry.inputs[3].default_value = (1.0, 1.0, 1.0)

        # Set locations
        group_input.location = (-823.9720458984375, -15.397307395935059)
        group_output.location = (453.2863464355469, 0.0)
        object_info.location = (-150.86984252929688, -76.18202209472656)
        sample_curve.location = (63.41365432739258, -107.25779724121094)
        transform_geometry.location = (251.88833618164062, 36.368404388427734)

        # Set dimensions
        group_input.width, group_input.height = 140.0, 100.0
        group_output.width, group_output.height = 140.0, 100.0
        object_info.width, object_info.height = 140.0, 100.0
        sample_curve.width, sample_curve.height = 140.0, 100.0
        transform_geometry.width, transform_geometry.height = 140.0, 100.0

        # Initialize geometry_nodes links
        # group_input.Object -> object_info.Object
        geometry_nodes.links.new(group_input.outputs[1], object_info.inputs[0])
        # object_info.Geometry -> sample_curve.Curves
        geometry_nodes.links.new(object_info.outputs[4], sample_curve.inputs[0])
        # sample_curve.Position -> transform_geometry.Translation
        geometry_nodes.links.new(sample_curve.outputs[1], transform_geometry.inputs[1])
        # group_input.Geometry -> transform_geometry.Geometry
        geometry_nodes.links.new(group_input.outputs[0], transform_geometry.inputs[0])
        # transform_geometry.Geometry -> group_output.Geometry
        geometry_nodes.links.new(transform_geometry.outputs[0], group_output.inputs[0])
        # group_input.Factor -> sample_curve.Factor
        geometry_nodes.links.new(group_input.outputs[2], sample_curve.inputs[2])

        return geometry_nodes


# Add menu entries
def snap_xy_menu_func(self, context):
    self.layout.operator(
        OBJECT_OT_align_to_active.bl_idname,
        text="Align Object (XY)",
        icon="SNAP_NORMAL",
    )


def move_group_menu_func(self, context):
    self.layout.operator(
        OBJECT_OT_align_collection.bl_idname, text="Align Collection (XY)", icon="GROUP"
    )


def create_arc_menu_func(self, context):
    self.layout.operator(
        OBJECT_OT_create_arc.bl_idname, text="Create Arc (XY)", icon="SPHERECURVE"
    )


def follow_path_menu_func(self, context):
    self.layout.operator(
        OBJECT_OT_follow_path.bl_idname, text="Follow Path", icon="CURVE_PATH"
    )


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
    # 4. Follow path operator
    bpy.utils.register_class(OBJECT_OT_follow_path)
    # 5. Main Typst import operator that handles file selection and import
    bpy.utils.register_class(ImportTypstOperator)
    # 6. File handler for drag-and-drop support of .txt/.typ files
    bpy.utils.register_class(TXT_FH_import)

    # Add menu entries
    # 1. Add Typst importer to the File > Import menu
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    # 2. Add arc creation to the Object menu
    bpy.types.VIEW3D_MT_object.prepend(create_arc_menu_func)
    # 3. Add XY snapping to the Object menu
    bpy.types.VIEW3D_MT_object.prepend(snap_xy_menu_func)
    # 4. Add group movement to the Object menu
    bpy.types.VIEW3D_MT_object.prepend(move_group_menu_func)
    # 5. Add follow path to the Object menu
    bpy.types.VIEW3D_MT_object.prepend(follow_path_menu_func)

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
    # 2. Remove from Object menu
    bpy.types.VIEW3D_MT_object.remove(snap_xy_menu_func)
    # 3. Remove group movement from Object menu
    bpy.types.VIEW3D_MT_object.remove(move_group_menu_func)
    # 4. Remove arc creation from Object menu
    bpy.types.VIEW3D_MT_object.remove(create_arc_menu_func)
    # 5. Remove follow path from Object menu
    bpy.types.VIEW3D_MT_object.remove(follow_path_menu_func)

    # Unregister Blender classes in reverse order
    bpy.utils.unregister_class(TXT_FH_import)
    bpy.utils.unregister_class(ImportTypstOperator)
    bpy.utils.unregister_class(OBJECT_OT_follow_path)
    bpy.utils.unregister_class(OBJECT_OT_create_arc)
    bpy.utils.unregister_class(OBJECT_OT_align_collection)
    bpy.utils.unregister_class(OBJECT_OT_align_to_active)


if __name__ == "__main__":
    register()
