import bpy
from bpy.props import StringProperty
import time
from bpy_extras.io_utils import ImportHelper
from .csv import load_csv
from .parsers import update_obj_from_csv
from pathlib import Path


# based on the blender docs: https://docs.blender.org/api/current/bpy.types.FileHandler.html#basic-filehandler-for-operator-that-imports-just-one-file
# and tweaked with this prompt: https://chatgpt.com/share/675b0831-354c-8013-bae0-9bb91d527f32


# Operator for the button and drag-and-drop
class ImportCsvPolarsOperator(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.import_csv_polars"
    bl_label = "Import CSV (Polars)"
    bl_options = {"PRESET", "UNDO"}

    # ImportHelper mix-in provides 'filepath' by default, but we redefine it here
    # to use SKIP_SAVE, allowing drag-and-drop to work properly.
    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})  # type: ignore

    filename_ext = ".txt"
    filter_glob: StringProperty(  # type: ignore
        default="*.txt",
        options={"HIDDEN"},
        maxlen=255,
    )

    def execute(self, context):
        # Ensure the filepath is a typ file

        if not self.filepath.lower().endswith(".txt"):
            self.report({"WARNING"}, "Selected file is not a typ")
            return {"CANCELLED"}

        start_time = time.perf_counter()

        print(self.filepath)

        import typst
        import tempfile
        import bpy

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

        # bob = load_csv(filepath=self.filepath)
        # bob.csv.filepath = self.filepath

        elapsed_time_sec = time.perf_counter() - start_time

        self.report(
            {"INFO"},
            f" 🐻‍❄️ 📥  Added {typst_file} in {elapsed_time_sec:.2f} ms",
        )
        # self.report(
        #     {"INFO"},
        #     f" 🐻‍❄️ 📥  Added {bob.name} in {elapsed_time_ms:.2f} ms",
        # )
        return {"FINISHED"}