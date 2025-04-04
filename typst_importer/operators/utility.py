import bpy
from .visibility import toggle_visibility




class OBJECT_OT_copy_without_keyframes(bpy.types.Operator):
    """
    Create a copy of selected objects without any keyframes and toggle visibility.
    Original objects are hidden and new copies are shown.
    """

    bl_idname = "object.copy_without_keyframes"
    bl_label = "Copy Without Keyframes"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.selected_objects

    def execute(self, context):
        current_frame = context.scene.frame_current
        copied_objects = []
        original_objects = list(context.selected_objects)  # Create a copy of the list

        for obj in original_objects:
            # Store the original object's collection
            obj_collections = []
            for collection in bpy.data.collections:
                if obj.name in collection.objects:
                    obj_collections.append(collection)

            # Select only this object and deselect others
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj

            # Duplicate the object
            bpy.ops.object.duplicate()
            new_obj = context.active_object
            new_obj.name = f"{obj.name}_static"
            
            # Clear all animation data from the new object
            if new_obj.animation_data:
                new_obj.animation_data_clear()
                
            # Clear all modifiers with keyframes
            for modifier in list(new_obj.modifiers):
                # Check if this is a modifier we typically use for animation
                if modifier.name in ["Visibility", "FollowPath"]:
                    new_obj.modifiers.remove(modifier)

            # Add to the list of copied objects
            copied_objects.append(new_obj)
            
            # Add the new object to the same collections as the original
            for collection in obj_collections:
                if new_obj.name not in collection.objects:
                    collection.objects.link(new_obj)

            # Toggle visibility of the original object to off
            toggle_visibility(obj, current_frame, make_visible=False)
            
            # Make the new object visible right away
            toggle_visibility(new_obj, current_frame, make_visible=True)

        # Reselect all the new objects
        bpy.ops.object.select_all(action='DESELECT')
        for obj in copied_objects:
            obj.select_set(True)
        
        if copied_objects:
            context.view_layer.objects.active = copied_objects[0]
        
        self.report(
            {"INFO"},
            f"Created {len(copied_objects)} static copies without keyframes"
        )
        return {"FINISHED"} 