import bpy


class OBJECT_OT_align_to_active(bpy.types.Operator):
    """
    Aligns selected objects' X and Y coordinates to match the active object's location, while preserving Z coordinates.

    Usage:
    1. Select one or more objects to align
    2. Select the target object last (making it active)
    3. Run the operator to align all selected objects to the active object's XY position
    """

    bl_idname = "object.align_object_xy"
    bl_label = "Align Object (XY)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.area is not None
            and context.area.type == "VIEW_3D"
            and context.active_object is not None
        )

    def execute(self, context):
        active_obj = context.active_object
        target_loc = (
            active_obj.location.copy()
        )  # Copy location to avoid direct reference issues
        for obj in context.selected_objects:
            if obj != active_obj:
                # Only snap X and Y; leave Z unchanged.
                obj.location.x = target_loc.x
                obj.location.y = target_loc.y
        return {"FINISHED"}


class OBJECT_OT_align_collection(bpy.types.Operator):
    """
    Aligns multiple collections of objects by moving them based on the active object's location.

    Usage:
    1. Select objects from different collections to align
    2. Select the target object last (making it active)
    3. Run the operator to move all collections to align with the active object
    """

    bl_idname = "object.align_collection_xy"
    bl_label = "Align Collection (XY)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.area is not None
            and context.area.type == "VIEW_3D"
            and context.active_object is not None
            and len(context.selected_objects) >= 2
        )

    def execute(self, context):
        # Need at least 2 objects selected
        if len(context.selected_objects) < 2:
            self.report(
                {"WARNING"},
                "Select at least 2 objects: source objects and destination object",
            )
            return {"CANCELLED"}

        # The active object is the destination
        destination = context.active_object

        # All other selected objects are sources
        source_objects = [obj for obj in context.selected_objects if obj != destination]

        # For each source object, move its entire collection
        for source in source_objects:
            # Compute the translation vector from source to destination
            delta = destination.location - source.location

            # Gather all objects in every collection that the source object is a member of,
            # including objects in sub-collections
            objects_to_move = set()

            def gather_objects_from_collection(collection):
                # Add objects directly in this collection
                objects_to_move.update(collection.objects)
                # Recursively process sub-collections
                for child_collection in collection.children:
                    gather_objects_from_collection(child_collection)

            if source.users_collection:
                for coll in source.users_collection:
                    gather_objects_from_collection(coll)
            else:
                # In case the source isn't in any collection (rare), move just the source
                objects_to_move.add(source)

            # Move each object by delta only in the X and Y axes, except for the destination
            for obj in objects_to_move:
                if obj == destination or obj in source_objects and obj != source:
                    continue
                obj.location.x += delta.x
                obj.location.y += delta.y

        self.report(
            {"INFO"}, f"Aligned {len(source_objects)} collections to {destination.name}"
        )
        return {"FINISHED"}
