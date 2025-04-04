import bpy
from ..node_groups import visibility_node_group


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