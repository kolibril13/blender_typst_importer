import bpy
from pathlib import Path
import databpy as db

class OBJECT_OT_import_curve_reveal(bpy.types.Operator):
    """
    Add an empty grease pencil object and import the HelloAnimate node tree
    """

    bl_idname = "object.import_curve_reveal"
    bl_label = "Import Curve Reveal"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            # Create an empty grease pencil object
            bpy.ops.object.grease_pencil_add(location=(0, 0, 0), type="EMPTY") 
            gp_obj = context.active_object
            gp_obj.name = "GreasePencil_CurveReveal"
            
            # Import the HelloAnimate node tree using databpy
            blend_file = Path(__file__).resolve().parent.parent / "ASSET_DIR" / "curve_reveal.blend"
            node_group_name = "HelloAnimate"
            
            node_group = db.nodes.append_from_blend(node_group_name, blend_file)
            
            # Print node names as in the provided snippet
            for node in node_group.nodes:
                print(node.name)
            
            # Add a geometry nodes modifier to the grease pencil object
            modifier = gp_obj.modifiers.new(name="HelloAnimate", type="NODES")
            modifier.node_group = node_group
            
            
            self.report(
                {"INFO"},
                f"Created grease pencil object '{gp_obj.name}' with HelloAnimate node tree in 'AnimationObjs' collection"
            )
            
            return {"FINISHED"}
            
        except Exception as e:
            self.report({"ERROR"}, f"Failed to import curve reveal setup: {str(e)}")
            return {"CANCELLED"} 