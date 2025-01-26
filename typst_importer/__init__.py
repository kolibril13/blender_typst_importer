# from .addon import register, unregister
# from .typst import load_typst


import bpy

class HELLO_OT_world(bpy.types.Operator):
    """Print 'Hello World' to the console"""
    bl_idname = "wm.hello_world"
    bl_label = "Hello World"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        print("Hello World")
        return {'FINISHED'}

class HELLO_PT_panel(bpy.types.Panel):
    """Creates a Panel in the 3D View's sidebar"""
    bl_label = "Hello World Panel"
    bl_idname = "VIEW3D_PT_hello_world"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hello World"

    def draw(self, context):
        layout = self.layout
        layout.operator("wm.hello_world")

def register():
    bpy.utils.register_class(HELLO_OT_world)
    bpy.utils.register_class(HELLO_PT_panel)

def unregister():
    bpy.utils.unregister_class(HELLO_PT_panel)
    bpy.utils.unregister_class(HELLO_OT_world)

if __name__ == "__main__":
    register()