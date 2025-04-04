from .utils import add_current_module_to_path
import bpy


# Import the operators from the operators package
from .operators import (
    OBJECT_OT_align_to_active,
    OBJECT_OT_align_collection,
    ImportTypstOperator,
    TXT_FH_import,
    OBJECT_OT_create_arc,
    OBJECT_OT_follow_path,
    OBJECT_OT_arc_and_follow,
    OBJECT_OT_hide_bezier_collection,
    OBJECT_OT_visibility_on,
    OBJECT_OT_visibility_off,
    OBJECT_OT_fade_in,
    OBJECT_OT_fade_in_to_plane,
    OBJECT_OT_fade_out,
    OBJECT_OT_hello_world,
)

# Global list to store our keymap entries for cleanup.
addon_keymaps = []


# Panel for the N-panel sidebar
class VIEW3D_PT_typst_animation_tools(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Typst Tools"
    bl_label = "Animation Tools"

    def draw(self, context):
        layout = self.layout

        # Alignment tools
        box = layout.box()
        box.label(text="Alignment")
        box.operator(
            OBJECT_OT_align_to_active.bl_idname,
            text="Align Object (XY)",
            icon="SNAP_NORMAL",
        )
        box.operator(
            OBJECT_OT_align_collection.bl_idname,
            text="Align Collection (XY)",
            icon="GROUP",
        )

        # Arc and path tools
        box = layout.box()
        box.label(text="Path Animation")
        box.operator(
            OBJECT_OT_create_arc.bl_idname, text="Create Arc (XY)", icon="SPHERECURVE"
        )
        box.operator(
            OBJECT_OT_follow_path.bl_idname, text="Follow Path", icon="CURVE_PATH"
        )
        box.operator(
            OBJECT_OT_arc_and_follow.bl_idname,
            text="Arc and Follow",
            icon="FORCE_CURVE",
        )
        box.operator(
            OBJECT_OT_hide_bezier_collection.bl_idname,
            text="Hide Bezier Curves",
            icon="HIDE_ON",
        )
        box.operator(
            OBJECT_OT_hello_world.bl_idname,
            text="Hello World",
            icon="INFO",
        )

        # Visibility tools
        box = layout.box()
        box.label(text="Visibility")
        row = box.row(align=True)
        row.operator(OBJECT_OT_visibility_on.bl_idname, text="On", icon="HIDE_OFF")
        row.operator(OBJECT_OT_visibility_off.bl_idname, text="Off", icon="HIDE_ON")

        # Fade tools
        box = layout.box()
        box.label(text="Fade Effects")
        box.operator(
            OBJECT_OT_fade_in.bl_idname, text="Fade In Objects", icon="TRIA_RIGHT"
        )
        box.operator(
            OBJECT_OT_fade_in_to_plane.bl_idname,
            text="Fade In (To Animation Plane)",
            icon="TRACKING_FORWARDS",
        )
        box.operator(
            OBJECT_OT_fade_out.bl_idname, text="Fade Out Objects", icon="TRIA_LEFT"
        )


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
    # 4. Arc and Follow operator
    bpy.utils.register_class(OBJECT_OT_arc_and_follow)
    # 5. Follow path operator
    bpy.utils.register_class(OBJECT_OT_follow_path)
    # 6. Visibility operators
    bpy.utils.register_class(OBJECT_OT_visibility_on)
    bpy.utils.register_class(OBJECT_OT_visibility_off)
    # 7. Fade operators
    bpy.utils.register_class(OBJECT_OT_fade_in)
    bpy.utils.register_class(OBJECT_OT_fade_in_to_plane)
    bpy.utils.register_class(OBJECT_OT_fade_out)
    # 8. Hide bezier curves operator
    bpy.utils.register_class(OBJECT_OT_hide_bezier_collection)
    # 9. Hello World operator
    bpy.utils.register_class(OBJECT_OT_hello_world)
    # 10. Main Typst import operator that handles file selection and import
    bpy.utils.register_class(ImportTypstOperator)
    # 11. File handler for drag-and-drop support of .txt/.typ files
    bpy.utils.register_class(TXT_FH_import)
    # 12. Register the sidebar panel
    bpy.utils.register_class(VIEW3D_PT_typst_animation_tools)

    # Add menu entries
    # 1. Add Typst importer to the File > Import menu
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

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

    # Unregister Blender classes in reverse order
    bpy.utils.unregister_class(VIEW3D_PT_typst_animation_tools)
    bpy.utils.unregister_class(TXT_FH_import)
    bpy.utils.unregister_class(ImportTypstOperator)
    bpy.utils.unregister_class(OBJECT_OT_hello_world)
    bpy.utils.unregister_class(OBJECT_OT_hide_bezier_collection)
    bpy.utils.unregister_class(OBJECT_OT_fade_out)
    bpy.utils.unregister_class(OBJECT_OT_fade_in_to_plane)
    bpy.utils.unregister_class(OBJECT_OT_fade_in)
    bpy.utils.unregister_class(OBJECT_OT_visibility_off)
    bpy.utils.unregister_class(OBJECT_OT_visibility_on)
    bpy.utils.unregister_class(OBJECT_OT_arc_and_follow)
    bpy.utils.unregister_class(OBJECT_OT_follow_path)
    bpy.utils.unregister_class(OBJECT_OT_create_arc)
    bpy.utils.unregister_class(OBJECT_OT_align_collection)
    bpy.utils.unregister_class(OBJECT_OT_align_to_active)


if __name__ == "__main__":
    register()
