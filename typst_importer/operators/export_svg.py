from pathlib import Path

import bpy
from bpy.props import StringProperty


# Default export path: user's Downloads folder
DEFAULT_EXPORT_PATH = str(Path.home() / "Downloads" / "typst_export.svg")


class ExportTypstSvgOperator(bpy.types.Operator):
    """Export the most recently generated Typst SVG to a file."""

    bl_idname = "export_scene.typst_svg"
    bl_label = "Export SVG"
    bl_options = {"REGISTER"}

    filepath: StringProperty(
        name="File Path",
        description="Path to save the exported SVG",
        default=DEFAULT_EXPORT_PATH,
        subtype="FILE_PATH",
    )

    def execute(self, context):
        # Use the last processed SVG stored on the scene (set after every Typst import)
        processed_svg = getattr(context.scene, "typst_last_processed_svg", None)

        if not processed_svg or not processed_svg.strip():
            self.report(
                {"ERROR"},
                "No Typst SVG found. Import Typst content first.",
            )
            return {"CANCELLED"}

        filepath = bpy.path.abspath(self.filepath) or DEFAULT_EXPORT_PATH
        if not filepath.lower().endswith(".svg"):
            filepath += ".svg"

        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            Path(filepath).write_text(processed_svg, encoding="utf-8")
        except OSError as e:
            self.report({"ERROR"}, f"Failed to write file: {e}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"SVG exported to {filepath}")
        return {"FINISHED"}

    def invoke(self, context, event):
        # Ensure default is Downloads if current path is empty
        if not self.filepath or not bpy.path.abspath(self.filepath):
            self.filepath = DEFAULT_EXPORT_PATH
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
