import bpy


class OBJECT_OT_hello_world(bpy.types.Operator):
    """Simple operator that prints Hello World"""

    bl_idname = "object.hello_world"
    bl_label = "Hello World"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        self.report({"INFO"}, "Hello World!")
        return {"FINISHED"} 