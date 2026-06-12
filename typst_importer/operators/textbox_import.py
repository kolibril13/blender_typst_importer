import bpy
from pathlib import Path
import tempfile
import time

from ..typst_to_svg import typst_to_blender_curves


class ImportFromTextboxOperator(bpy.types.Operator):
    """Base operator for importing from the textbox"""
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # Get the textbox content
        text_content = context.scene.typst_text
        if not text_content.strip():
            self.report({"WARNING"}, "Textbox is empty")
            return {"CANCELLED"}

        # Get options from window manager
        wm = context.window_manager
        use_custom_header = getattr(wm, "typst_use_custom_header", False)
        origin_to_char = getattr(wm, "typst_origin_to_char", False)

        # Apply custom header if checkbox is checked
        if use_custom_header:
            default_header = """#set page(width: auto, height: auto, margin: 0cm, fill: none)
#set text(size: 50pt)
"""
            final_content = default_header + text_content
        else:
            final_content = text_content

        # Write content to temporary file
        temp_dir = Path(tempfile.gettempdir())
        temp_file = temp_dir / "typst_textbox.txt"
        temp_file.write_text(final_content)

        # Start timer
        start_time = time.perf_counter()

        # Import based on subclass implementation
        try:
            collection = self.import_typst(temp_file, origin_to_char)
            elapsed_time_ms = (time.perf_counter() - start_time) * 1000
            self.report(
                {"INFO"},
                f"🦢 Typst Importer: textbox content rendered in {elapsed_time_ms:.2f} ms as {collection.name}",
            )
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Import failed: {str(e)}")
            return {"CANCELLED"}
        finally:
            # Clean up temporary file
            if temp_file.exists():
                temp_file.unlink()

    def import_typst(self, typst_file: Path, origin_to_char: bool = False):
        """Override in subclasses to specify import type"""
        raise NotImplementedError


class ImportFromTextboxAsCurveOperator(ImportFromTextboxOperator):
    """Import textbox content as curves"""
    bl_idname = "import_scene.import_textbox_curve"
    bl_label = "Import from Textbox as Curve"

    def import_typst(self, typst_file: Path, origin_to_char: bool = False):
        return typst_to_blender_curves(
            typst_file,
            convert_to_mesh=False,
            origin_to_char=origin_to_char,
        )


class ImportFromTextboxAsMeshOperator(ImportFromTextboxOperator):
    """Import textbox content as mesh"""
    bl_idname = "import_scene.import_textbox_mesh"
    bl_label = "Import from Textbox as Mesh"

    def import_typst(self, typst_file: Path, origin_to_char: bool = False):
        return typst_to_blender_curves(
            typst_file,
            convert_to_mesh=True,
            origin_to_char=origin_to_char,
        )


class ImportFromTextboxAsUnfilledCurveOperator(ImportFromTextboxOperator):
    """Import textbox content as unfilled curves"""
    bl_idname = "import_scene.import_textbox_unfilled_curve"
    bl_label = "Import from Textbox as Unfilled Curve"

    def import_typst(self, typst_file: Path, origin_to_char: bool = False):
        return typst_to_blender_curves(
            typst_file,
            convert_to_mesh=False,
            convert_to_unfilled_path=True,
            origin_to_char=origin_to_char,
        )
