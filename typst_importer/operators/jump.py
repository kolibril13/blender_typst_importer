import bpy


class OBJECT_OT_apply_jump(bpy.types.Operator):
    """Print 'Jump'."""

    bl_idname = "object.apply_jump"
    bl_label = "Apply Jump"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        print("Jump")
        return {"FINISHED"}
