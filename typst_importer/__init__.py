import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty

from pathlib import Path
import typst
import tempfile
import time

# Operator for the button and drag-and-drop
class ImportTxtPolarsOperator(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.import_txt_polars"
    bl_label = "Import TXT (Polars)"
    bl_options = {"PRESET", "UNDO"}

    print("ImportTxtPolarsOperator")
    # ImportHelper mix-in provides 'filepath' by default, but we redefine it here
    # to use SKIP_SAVE, allowing drag-and-drop to work properly.
    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})

    filename_ext = ".txt"
    filter_glob: StringProperty(default="*.txt", options={"HIDDEN"}, maxlen=255)

    def execute(self, context):
        # Ensure the filepath is a TXT file
        if not self.filepath.lower().endswith(".txt"):
            self.report({"WARNING"}, "Selected file is not a TXT")
            return {"CANCELLED"}

        # Use the selected/dropped file path
        typst_file = Path(self.filepath)
        file_name_without_ext = typst_file.stem
        start_time = time.perf_counter()

        temp_dir = Path(tempfile.gettempdir())
        svg_file = temp_dir / "hello.svg"

        typst.compile(typst_file, format="svg", output=str(svg_file))

        bpy.ops.import_curve.svg(filepath=str(svg_file))
        col = bpy.context.scene.collection.children["hello.svg"]
        col.name = "Formula"

        elapsed_time_ms = (time.perf_counter() - start_time) * 1000

        self.report(
            {"INFO"},
            f" 🐻‍❄️ 📥  Added {typst_file} in {elapsed_time_ms:.2f} ms",
        )
        return {"FINISHED"}

    def invoke(self, context, event):
        # If the filepath is already set (e.g. drag-and-drop), execute directly
        if self.filepath:
            return self.execute(context)
        # Otherwise, show the file browser
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


# File Handler for drag-and-drop support
class TXT_FH_import(bpy.types.FileHandler):
    bl_idname = "TXT_FH_import"
    bl_label = "File handler for TXT import"
    bl_import_operator = "import_scene.import_txt_polars"
    bl_file_extensions = ".txt"

    @classmethod
    def poll_drop(cls, context):
        # Allow drag-and-drop in the 3D View
        return context.area


# Register the operator and menu entry
def menu_func_import(self, context):
    self.layout.operator(ImportTxtPolarsOperator.bl_idname, text="TXT 🐻 (.txt)")


class HelloWorldWorldPanel(bpy.types.Panel):
    bl_label = "Hello World Panel"
    bl_idname = "WORLD_PT_hello_world"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "world"  # Ensures the panel appears in the World tab

    def draw(self, context):
        layout = self.layout
        layout.label(text="Hello World!")
        layout.operator(ImportTxtPolarsOperator.bl_idname, text="Import TXT 🐻")


def register():
    bpy.utils.register_class(ImportTxtPolarsOperator)
    bpy.utils.register_class(TXT_FH_import)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.utils.register_class(HelloWorldWorldPanel)


def unregister():
    bpy.utils.unregister_class(HelloWorldWorldPanel)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(TXT_FH_import)
    bpy.utils.unregister_class(ImportTxtPolarsOperator)


if __name__ == "__main__":
    register()