import bpy
from .visibility import toggle_visibility
from .collections import get_or_create_collection


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




class OBJECT_OT_fade_in_to_plane(bpy.types.Operator):
    """Fade in selected objects and move copies to the animation plane (AnimationObjs collection)"""

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

        # Get or create the "AnimationObjs" collection
        target_collection = get_or_create_collection("AnimationObjs")

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
            f"Created and fading in {len(created_objects)} objects in collection 'AnimationObjs'",
        )
        return {"FINISHED"}


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