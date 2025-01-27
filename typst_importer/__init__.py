import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty

from pathlib import Path
import typst
import tempfile
import time


# Operator for the button and drag-and-drop
class ImportTypstOperator(bpy.types.Operator, ImportHelper):
    """Operator to import a .txt file, compile it via Typst, and import as SVG in Blender."""

    bl_idname = "import_scene.import_txt_typst"
    bl_label = "Import TXT (Typst)"
    bl_options = {"PRESET", "UNDO"}

    # ImportHelper mix-in provides 'filepath' by default, but we redefine it here
    # to use SKIP_SAVE, allowing drag-and-drop to work properly.
    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})

    filename_ext = ".txt"
    filter_glob: StringProperty(default="*.txt", options={"HIDDEN"}, maxlen=255)

    def execute(self, context):
        # Check that it's really a .txt file
        if not self.filepath.lower().endswith(".txt"):
            self.report({"WARNING"}, "Selected file is not a TXT")
            return {"CANCELLED"}

        # Prepare the file variables
        typst_file = Path(self.filepath)
        file_name_without_ext = typst_file.stem

        # Start timing
        start_time = time.perf_counter()

        # Create a temp SVG path
        temp_dir = Path(tempfile.gettempdir())
        svg_file_name = f"{file_name_without_ext}.svg"
        svg_file = temp_dir / svg_file_name

        # Compile the input .txt file to an SVG via Typst
        typst.compile(typst_file, format="svg", output=str(svg_file))

        # Import the generated SVG
        bpy.ops.import_curve.svg(filepath=str(svg_file))

        # Rename the newly created Collection
        # By default, the new collection is named after the file name e.g. 'myfile.svg'
        imported_collection = bpy.context.scene.collection.children.get(svg_file_name)
        if imported_collection:
            imported_collection.name = f"Formula_{file_name_without_ext}"
        else:
            # Fallback in case Blender changes how new collections are named
            self.report(
                {"WARNING"}, "Could not find the imported collection to rename."
            )

        elapsed_time_ms = (time.perf_counter() - start_time) * 1000

        self.report(
            {"INFO"}, f" 🦢  Added {typst_file.name} in {elapsed_time_ms:.2f} ms"
        )
        return {"FINISHED"}

    def invoke(self, context, event):
        # If the filepath is set (drag-and-drop scenario), execute directly
        if self.filepath:
            return self.execute(context)
        # Otherwise, show the file browser
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


# File Handler for drag-and-drop support
class TXT_FH_import(bpy.types.FileHandler):
    """A file handler to allow .txt files to be dragged and dropped directly into Blender."""

    bl_idname = "TXT_FH_import"
    bl_label = "File handler for TXT import (Typst)"
    bl_import_operator = "import_scene.import_txt_typst"
    bl_file_extensions = ".txt"

    @classmethod
    def poll_drop(cls, context):
        # Allow drag-and-drop
        return context.area


def menu_func_import(self, context):
    """Function to add an entry into the File > Import menu."""
    self.layout.operator(ImportTypstOperator.bl_idname, text="Typst 🦢 via (.txt)")


def register():
    bpy.utils.register_class(ImportTypstOperator)
    bpy.utils.register_class(TXT_FH_import)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(TXT_FH_import)
    bpy.utils.unregister_class(ImportTypstOperator)


if __name__ == "__main__":
    register()
