from .utils import add_current_module_to_path
import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from pathlib import Path
import time

# Import the helper function from typst_to_svg.py
from .typst_to_svg import compile_and_import_typst

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
        svg_file = compile_and_import_typst(typst_file) 
        # TODO: maybe return the blender object here?
        
        # Attempt to rename the newly created Collection
        imported_collection = bpy.context.scene.collection.children.get(svg_file.name)
        if imported_collection:
            imported_collection.name = f"Formula_{file_name_without_ext}"
        else:
            self.report({"WARNING"}, "Could not find the imported collection to rename.")

        elapsed_time_ms = (time.perf_counter() - start_time) * 1000
        self.report({"INFO"}, f" 🦢  Added {typst_file.name} in {elapsed_time_ms:.2f} ms")
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
    add_current_module_to_path()
    bpy.utils.register_class(ImportTypstOperator)
    bpy.utils.register_class(TXT_FH_import)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(TXT_FH_import)
    bpy.utils.unregister_class(ImportTypstOperator)


if __name__ == "__main__":
    register()