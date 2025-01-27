import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty

from pathlib import Path
import typst
import tempfile
import bpy

from io import StringIO
from pathlib import Path
import time

# based on the blender docs: https://docs.blender.org/api/current/bpy.types.FileHandler.html#basic-filehandler-for-operator-that-imports-just-one-file
# and tweaked with this prompt: https://chatgpt.com/share/675b0831-354c-8013-bae0-9bb91d527f32


# Operator for the button and drag-and-drop
class ImportCsvPolarsOperator(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.import_csv_polars"
    bl_label = "Import CSV (Polars)"
    bl_options = {"PRESET", "UNDO"}

    # ImportHelper mix-in provides 'filepath' by default, but we redefine it here
    # to use SKIP_SAVE, allowing drag-and-drop to work properly.
    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})

    filename_ext = ".csv"
    filter_glob: StringProperty(default="*.csv", options={"HIDDEN"}, maxlen=255)

    def execute(self, context):
        # Ensure the filepath is a CSV file

        if not self.filepath.lower().endswith(".csv"):
            self.report({"WARNING"}, "Selected file is not a CSV")
            return {"CANCELLED"}

        # Use the selected/dropped file path
        csv_file = Path(self.filepath)
        file_name_without_ext = csv_file.stem
        start_time = time.perf_counter()

        temp_dir = Path(tempfile.gettempdir())

        typst_file = temp_dir / "hello.typ"
        svg_file = temp_dir / "hello.svg"

        file_content = """
        #set page(width: auto, height: auto, margin: 0cm, fill: none)
        #set text(size: 5000pt)
        $ sum_(k=1)^n k = (n(n+1)) / 2 $
        """
        typst_file.write_text(file_content)
        typst.compile(typst_file, format="svg", output=str(svg_file))

        bpy.ops.import_curve.svg(filepath=str(svg_file))
        col = bpy.context.scene.collection.children["hello.svg"]
        col.name = "Formula"

        elapsed_time_ms = (time.perf_counter() - start_time) * 1000

        self.report(
            {"INFO"},
            f" 🐻‍❄️ 📥  Added {csv_file} in {elapsed_time_ms:.2f} ms",
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
class CSV_FH_import(bpy.types.FileHandler):
    bl_idname = "CSV_FH_import"
    bl_label = "File handler for CSV import"
    bl_import_operator = "import_scene.import_csv_polars"
    bl_file_extensions = ".csv"

    @classmethod
    def poll_drop(cls, context):
        # Allow drag-and-drop in the 3D View
        return context.area


# Register the operator and menu entry
def menu_func_import(self, context):
    self.layout.operator(ImportCsvPolarsOperator.bl_idname, text="CSV 🐻 (.csv)")


class HelloWorldWorldPanel(bpy.types.Panel):
    bl_label = "Hello World Panel"
    bl_idname = "WORLD_PT_hello_world"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "world"  # Ensures the panel appears in the World tab

    def draw(self, context):
        layout = self.layout
        layout.label(text="Hello World!")
        layout.operator(ImportCsvPolarsOperator.bl_idname, text="Import CSV 🐻")


def register():
    bpy.utils.register_class(ImportCsvPolarsOperator)
    bpy.utils.register_class(CSV_FH_import)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.utils.register_class(HelloWorldWorldPanel)


def unregister():
    bpy.utils.unregister_class(HelloWorldWorldPanel)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(CSV_FH_import)
    bpy.utils.unregister_class(ImportCsvPolarsOperator)


if __name__ == "__main__":
    register()
