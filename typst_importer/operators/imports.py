import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import BoolProperty, FloatProperty, StringProperty
from pathlib import Path
import time

from ..typst_to_svg import typst_to_blender_curves


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
    allow_external_images: BoolProperty(
        name="Allow Images Outside Typst Folder",
        description=(
            "Allow absolute paths and parent-directory image references; "
            "leave disabled for untrusted Typst files"
        ),
        default=False,
    )
    import_extruded: BoolProperty(
        name="Import Extruded",
        description="Extrude every imported element along the Z axis",
        default=False,
    )
    extrude_depth: FloatProperty(
        name="Extrude Depth",
        description="Thickness toward the front (+Z); the back face stays at the origin",
        default=0.04,
        min=0.0,
        soft_max=0.2,
        step=0.1,
        precision=3,
        subtype="DISTANCE",
    )
    shade_auto_smooth: BoolProperty(
        name="Shade Auto Smooth",
        description="Add a Smooth by Angle modifier to every imported element",
        default=False,
    )
    # Operator properties cannot point at a Material, so store its name.
    custom_material: StringProperty(
        name="Material",
        description="Use this material for every imported element instead of the Typst colors",
        default="",
    )

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
        collection = typst_to_blender_curves(
            typst_file,
            allow_external_images=self.allow_external_images,
            extrude=self.extrude_depth if self.import_extruded else 0.0,
            shade_auto_smooth=self.shade_auto_smooth,
            material=bpy.data.materials.get(self.custom_material),
        )

        elapsed_time_ms = (time.perf_counter() - start_time) * 1000
        self.report(
            {"INFO"},
            f" 🦢  Typst Importer: {typst_file.name} rendered in {elapsed_time_ms:.2f} ms as {collection.name}",
        )
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "allow_external_images")
        layout.prop(self, "import_extruded")
        row = layout.row()
        row.enabled = self.import_extruded
        row.prop(self, "extrude_depth")
        layout.prop(self, "shade_auto_smooth")
        layout.prop_search(self, "custom_material", bpy.data, "materials")

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
