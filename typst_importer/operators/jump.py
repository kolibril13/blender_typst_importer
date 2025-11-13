import bpy
from pathlib import Path
import databpy as db

class OBJECT_OT_apply_jump(bpy.types.Operator):
    """Add 'Jump' Geometry Nodes modifier."""

    bl_idname = "object.add_jump_geonodes_modifier"
    bl_label = "Add Jump GeoNodes Modifier"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        active_obj = context.active_object
        print("Adding Jump GeoNodes Modifier")
        print(f"Active object: {active_obj.name if active_obj else None}")

        blend_file = Path(__file__).parent.parent / "blender_assets.blend"
        node_group_dir = str(blend_file) + "/NodeTree/"
        node_group_name = "JUMP"
        node_group = db.nodes.append_from_blend(node_group_name, node_group_dir)
        modifier = active_obj.modifiers.new(name="GeoNodes", type='NODES')
        modifier.node_group = node_group
        return {"FINISHED"}
