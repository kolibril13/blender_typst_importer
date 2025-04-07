import bpy
from ..node_groups import visibility_node_group
from .op_utils import get_or_create_collection


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
    obj.keyframe_insert('modifiers["Visibility"]["Socket_2"]', frame=current_frame-1)

    # Set target state at next frame
    target_state = make_visible
    visibility_modifier["Socket_2"] = target_state
    obj.keyframe_insert('modifiers["Visibility"]["Socket_2"]', frame=current_frame)

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


class OBJECT_OT_join_on_objects_off(bpy.types.Operator):
    """
    Create a joined object from selected objects, make the joined object visible and the individual objects invisible
    """

    bl_idname = "object.join_on_objects_off"
    bl_label = "Join: Objects -> Joined"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0

    def execute(self, context):
        # Get the current frame
        current_frame = context.scene.frame_current

        # Get or create the AnimationObjs collection
        target_collection = get_or_create_collection("AnimationObjs")

        # Store selected objects
        selected_objects = list(context.selected_objects)

        # Create a copy of the selected objects before joining
        original_objects = selected_objects.copy()

        # Join all selected objects
        if len(selected_objects) > 1:
            # Duplicate the objects first
            bpy.ops.object.duplicate()
            # Get the duplicated objects
            duplicated_objects = context.selected_objects

            # Set the active object (target for joining)
            context.view_layer.objects.active = duplicated_objects[0]

            # Join objects
            bpy.ops.object.join()

            # The joined object is now the active object
            joined_object = context.active_object
            # Rename the joined object
            joined_object.name = "Joined_Group"
            joined_object.select_set(True)

            # Move the joined object to the AnimationObjs collection
            # First remove from current collections
            for collection in bpy.data.collections:
                if joined_object.name in collection.objects:
                    collection.objects.unlink(joined_object)
            
            # Add to target collection
            target_collection.objects.link(joined_object)

            # Make the joined object visible
            toggle_visibility(joined_object, current_frame, True)

            # Make the original objects invisible
            for obj in original_objects:
                toggle_visibility(obj, current_frame, False)

            self.report(
                {"INFO"},
                f"Created joined group in 'AnimationObjs' collection and toggled visibility for {len(original_objects)} objects",
            )


        return {"FINISHED"}


class OBJECT_OT_join_to_plane(bpy.types.Operator):
    """
    Create a joined object from selected objects at z=0 with visibility on
    """

    bl_idname = "object.join_to_plane"
    bl_label = "Join to Animation Plane"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0

    def execute(self, context):
        # Get the current frame
        current_frame = context.scene.frame_current

        # Get or create the AnimationObjs collection
        target_collection = get_or_create_collection("AnimationObjs")

        # Store selected objects
        selected_objects = list(context.selected_objects)

        # Join all selected objects
        if len(selected_objects) > 1:
            # Duplicate the objects first
            bpy.ops.object.duplicate()
            # Get the duplicated objects
            duplicated_objects = context.selected_objects

            # Set the active object (target for joining)
            context.view_layer.objects.active = duplicated_objects[0]

            # Join objects
            bpy.ops.object.join()

            # The joined object is now the active object
            joined_object = context.active_object
            # Rename the joined object
            joined_object.name = "Joined_Group_Plane"
            joined_object.select_set(True)
            
            # Set z coordinate to 0
            joined_object.location.z = 0

            # Move the joined object to the AnimationObjs collection
            # First remove from current collections
            for collection in bpy.data.collections:
                if joined_object.name in collection.objects:
                    collection.objects.unlink(joined_object)
            
            # Add to target collection
            target_collection.objects.link(joined_object)

            # Make the joined object visible
            toggle_visibility(joined_object, current_frame, True)

            self.report(
                {"INFO"},
                f"Created joined group at z=0 in 'AnimationObjs' collection with visibility on",
            )

        return {"FINISHED"}


class OBJECT_OT_copy_to_plane(bpy.types.Operator):
    """
    Create copies of selected objects at z=0 with opacity set to 1
    """

    bl_idname = "object.copy_to_plane"
    bl_label = "Copy to Animation Plane"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0

    def execute(self, context):
        # Get the current frame
        current_frame = context.scene.frame_current

        # Get or create the AnimationObjs collection
        target_collection = get_or_create_collection("AnimationObjs")

        # Store selected objects
        selected_objects = list(context.selected_objects)
        created_objects = []

        for obj in selected_objects:
            # Deselect all objects
            bpy.ops.object.select_all(action="DESELECT")
            
            # Select only this object
            obj.select_set(True)
            context.view_layer.objects.active = obj
            
            # Duplicate the object
            bpy.ops.object.duplicate()
            
            # Get the newly created copy
            copy_obj = context.active_object
            copy_obj.name = f"{obj.name}_plane"
            
            # Set z coordinate to 0
            copy_obj.location.z = 0
            
            # Move the copy to the AnimationObjs collection
            # First remove from current collections
            for collection in bpy.data.collections:
                if copy_obj.name in collection.objects:
                    collection.objects.unlink(copy_obj)
            
            # Add to target collection
            target_collection.objects.link(copy_obj)
            
            # Make the object visible
            toggle_visibility(copy_obj, current_frame, True)
            
            # Ensure the opacity property exists
            if "opacity" not in copy_obj:
                copy_obj["opacity"] = 0.0
            
            # Set opacity to 1
            copy_obj["opacity"] = 1.0
            copy_obj.keyframe_insert(data_path='["opacity"]', frame=current_frame)
            
            created_objects.append(copy_obj.name)

        # Select all the newly created objects
        bpy.ops.object.select_all(action="DESELECT")
        for obj_name in created_objects:
            if obj_name in bpy.data.objects:
                bpy.data.objects[obj_name].select_set(True)

        self.report(
            {"INFO"},
            f"Created {len(created_objects)} individual copies at z=0 in 'AnimationObjs' collection with opacity set to 1",
        )
        

        return {"FINISHED"}
    


    
class OBJECT_OT_join_off_objects_on(bpy.types.Operator):
    """
    Create a joined object from selected objects, make the joined object invisible and the individual objects visible
    """

    bl_idname = "object.join_off_objects_on"
    bl_label = "Join: Joined -> Objects"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0

    def execute(self, context):
        # Get the current frame
        current_frame = context.scene.frame_current

        # Get or create the AnimationObjs collection
        target_collection = get_or_create_collection("AnimationObjs")

        # Store selected objects
        selected_objects = list(context.selected_objects)

        # Create a copy of the selected objects before joining
        original_objects = selected_objects.copy()

        # Join all selected objects
        if len(selected_objects) > 1:
            # Duplicate the objects first
            bpy.ops.object.duplicate()
            # Get the duplicated objects
            duplicated_objects = context.selected_objects

            # Set the active object (target for joining)
            context.view_layer.objects.active = duplicated_objects[0]

            # Join objects
            bpy.ops.object.join()

            # The joined object is now the active object
            joined_object = context.active_object
            # Rename the joined object
            joined_object.name = "Joined_Group"
            joined_object.select_set(True)

            # Move the joined object to the AnimationObjs collection
            # First remove from current collections
            for collection in bpy.data.collections:
                if joined_object.name in collection.objects:
                    collection.objects.unlink(joined_object)
            
            # Add to target collection
            target_collection.objects.link(joined_object)

            # Make the joined object invisible (opposite of the other operator)
            toggle_visibility(joined_object, current_frame, False)

            # Make the original objects visible (opposite of the other operator)
            for obj in original_objects:
                toggle_visibility(obj, current_frame, True)

            self.report(
                {"INFO"},
                f"Created joined group in 'AnimationObjs' collection and toggled visibility for {len(original_objects)} objects",
            )


        return {"FINISHED"}
