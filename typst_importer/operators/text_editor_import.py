import bpy
from bpy.props import StringProperty
from pathlib import Path
import tempfile
import time

from ..typst_to_svg import typst_to_blender_curves


class ImportFromTextEditorOperator(bpy.types.Operator):
    """Base operator for importing from text editor"""
    bl_options = {"REGISTER", "UNDO"}
    
    text_name: StringProperty(
        name="Text Name",
        description="Name of the text document in Blender's text editor",
    )
    
    def execute(self, context):
        # Get the text data block
        text_data = bpy.data.texts.get(self.text_name)
        if not text_data:
            self.report({"ERROR"}, f"Text document '{self.text_name}' not found")
            return {"CANCELLED"}
        
        # Get the text content
        text_content = text_data.as_string()
        if not text_content.strip():
            self.report({"WARNING"}, f"Text document '{self.text_name}' is empty")
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
        
        # Determine file extension based on text name or default to .txt
        if self.text_name.lower().endswith(('.txt', '.typ')):
            ext = Path(self.text_name).suffix
        else:
            ext = '.txt'
        
        # Write content to temporary file
        temp_dir = Path(tempfile.gettempdir())
        temp_file = temp_dir / f"{self.text_name}{ext}"
        temp_file.write_text(final_content)
        
        # Start timer
        start_time = time.perf_counter()
        
        # Import based on subclass implementation
        try:
            collection = self.import_typst(temp_file, origin_to_char)
            elapsed_time_ms = (time.perf_counter() - start_time) * 1000
            self.report(
                {"INFO"},
                f"🦢 Typst Importer: {self.text_name} rendered in {elapsed_time_ms:.2f} ms as {collection.name}",
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


class ImportFromTextEditorAsCurveOperator(ImportFromTextEditorOperator):
    """Import text editor document as curves"""
    bl_idname = "import_scene.import_text_editor_curve"
    bl_label = "Import from Text Editor as Curve"
    
    def import_typst(self, typst_file: Path, origin_to_char: bool = False):
        return typst_to_blender_curves(
            typst_file,
            convert_to_mesh=False,
            use_grease_pencil=False,
            origin_to_char=origin_to_char,
        )


class ImportFromTextEditorAsMeshOperator(ImportFromTextEditorOperator):
    """Import text editor document as mesh"""
    bl_idname = "import_scene.import_text_editor_mesh"
    bl_label = "Import from Text Editor as Mesh"
    
    def import_typst(self, typst_file: Path, origin_to_char: bool = False):
        return typst_to_blender_curves(
            typst_file,
            convert_to_mesh=True,
            use_grease_pencil=False,
            origin_to_char=origin_to_char,
        )


class ImportFromTextEditorAsGreasePencilOperator(ImportFromTextEditorOperator):
    """Import text editor document as grease pencil"""
    bl_idname = "import_scene.import_text_editor_grease_pencil"
    bl_label = "Import from Text Editor as Grease Pencil"
    
    def import_typst(self, typst_file: Path, origin_to_char: bool = False):
        return typst_to_blender_curves(
            typst_file,
            convert_to_mesh=False,
            use_grease_pencil=True,
            origin_to_char=origin_to_char,
        )


class ImportFromTextEditorAsUnfilledCurveOperator(ImportFromTextEditorOperator):
    """Import text editor document as unfilled curves"""
    bl_idname = "import_scene.import_text_editor_unfilled_curve"
    bl_label = "Import from Text Editor as Unfilled Curve"
    
    def import_typst(self, typst_file: Path, origin_to_char: bool = False):
        return typst_to_blender_curves(
            typst_file,
            convert_to_mesh=False,
            use_grease_pencil=False,
            convert_to_unfilled_path=True,
            origin_to_char=origin_to_char,
        )

