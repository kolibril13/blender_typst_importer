from .utils import add_current_module_to_path
import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from pathlib import Path
import time

# Global list to store our keymap entries for cleanup.
addon_keymaps = []

class OBJECT_OT_snap_xy(bpy.types.Operator):
    """Snap selected objects' X and Y to the active object's X and Y location (Z remains unchanged)"""
    bl_idname = "object.snap_xy"
    bl_label = "Snap XY to Active"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.area is not None and 
                context.area.type == 'VIEW_3D' and 
                context.active_object is not None)

    def execute(self, context):
        active_obj = context.active_object
        target_loc = active_obj.location.copy()  # Copy location to avoid direct reference issues
        for obj in context.selected_objects:
            if obj != active_obj:
                # Only snap X and Y; leave Z unchanged.
                obj.location.x = target_loc.x
                obj.location.y = target_loc.y
        return {'FINISHED'}

# Add a menu entry in the Object menu with a nice icon.
def snap_xy_menu_func(self, context):
    self.layout.operator(OBJECT_OT_snap_xy.bl_idname, text="Snap XY to Active", icon='SNAP_NORMAL')

# Import the helper function from typst_to_svg.py
from .typst_to_svg import typst_to_blender_curves


# Operator for the button and drag-and-drop
class ImportTypstOperator(bpy.types.Operator, ImportHelper):
    """Operator to import a .txt or .typ file, compile it via Typst, and import as SVG in Blender."""

    bl_idname = "import_scene.import_txt_typst"
    bl_label = "Import Typst File (.txt/.typ)"
    bl_options = {"PRESET", "UNDO"}

    # ImportHelper provides a default 'filepath' property,
    # but we redefine it here with SKIP_SAVE to support drag–n–drop.
    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})

    # Set a default extension (the user can change it in the file browser)
    filename_ext = ".txt"
    filter_glob: StringProperty(default="*.txt;*.typ", options={"HIDDEN"}, maxlen=255)

    def execute(self, context):
        # Verify that the selected file is either a .txt or .typ file.
        if not self.filepath.lower().endswith((".txt", ".typ")):
            self.report({"WARNING"}, "Selected file is not a TXT or TYP file")
            return {"CANCELLED"}

        # Prepare file variables
        typst_file = Path(self.filepath)
        file_name_without_ext = typst_file.stem

        # Start the timer
        start_time = time.perf_counter()

        # Compile and import the file using our helper function
        collection = typst_to_blender_curves(typst_file)

        elapsed_time_ms = (time.perf_counter() - start_time) * 1000
        self.report(
            {"INFO"},
            f" 🦢  Typst Importer: {typst_file.name} rendered in {elapsed_time_ms:.2f} ms as {collection.name}",
        )
        return {"FINISHED"}

    def invoke(self, context, event):
        # If the operator was invoked with a filepath (drag–n–drop), execute directly.
        if self.filepath:
            return self.execute(context)
        # Otherwise, open the file browser.
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


# File Handler for drag-and-drop support
class TXT_FH_import(bpy.types.FileHandler):
    """A file handler to allow .txt and .typ files to be dragged and dropped directly into Blender."""

    bl_idname = "TXT_FH_import"
    bl_label = "File handler for TXT/TYP import (Typst)"
    bl_import_operator = "import_scene.import_txt_typst"
    bl_file_extensions = ".txt;.typ"

    @classmethod
    def poll_drop(cls, context):
        # Allow drag–n–drop
        return context.area is not None


def menu_func_import(self, context):
    """Add an entry into the File > Import menu."""
    self.layout.operator(ImportTypstOperator.bl_idname, text="Typst 🦢 via (.txt/.typ)")


def register():
    # Add the current module to Python's path to ensure imports work correctly
    add_current_module_to_path()

    # Register Blender classes (operators and file handler)
    # 1. XY snapping operator for aligning objects
    bpy.utils.register_class(OBJECT_OT_snap_xy)
    # 2. Main Typst import operator that handles file selection and import
    bpy.utils.register_class(ImportTypstOperator)
    # 3. File handler for drag-and-drop support of .txt/.typ files
    bpy.utils.register_class(TXT_FH_import)

    # Add menu entries
    # 1. Add Typst importer to the File > Import menu
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    # 2. Add XY snapping to the Object menu
    bpy.types.VIEW3D_MT_object.prepend(snap_xy_menu_func)
    
    # Set up keyboard shortcut
    # Create a new keymap for the XY snap operator in Object Mode
    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name='Object Mode', space_type='EMPTY')
    # Bind the 'J' key to trigger the XY snap operator
    kmi = km.keymap_items.new(OBJECT_OT_snap_xy.bl_idname, type='J', value='PRESS')
    # Store keymap for proper cleanup on unregister
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
    # 2. Remove from Object menu
    bpy.types.VIEW3D_MT_object.remove(snap_xy_menu_func)

    # Unregister Blender classes in reverse order
    bpy.utils.unregister_class(TXT_FH_import)
    bpy.utils.unregister_class(ImportTypstOperator)
    bpy.utils.unregister_class(OBJECT_OT_snap_xy)


if __name__ == "__main__":
    register()
