import bpy
from mathutils import Vector


def get_curve_collection_bounds(collection):
    """
    Calculate the bounding box dimensions of a collection containing curves and/or meshes.

    Args:
        collection: Blender collection object containing curves and/or meshes

    Returns:
        tuple: ((min_x, min_y, min_z), (max_x, max_y, max_z))
        The minimum and maximum coordinates of the bounding box
    """
    # Initialize bounds
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")

    # Get the dependency graph
    depsgraph = bpy.context.evaluated_depsgraph_get()

    # Iterate through objects in collection
    for obj in collection.objects:
        if obj.type in ("CURVE", "MESH"):
            # Get evaluated version of the object
            eval_obj = obj.evaluated_get(depsgraph)

            # Create mesh from evaluated object
            temp_mesh = eval_obj.to_mesh()

            # Calculate bounds using mesh vertices in world space
            for vert in temp_mesh.vertices:
                world_vert = obj.matrix_world @ vert.co
                # Update bounds
                min_x = min(min_x, world_vert.x)
                min_y = min(min_y, world_vert.y)
                min_z = min(min_z, world_vert.z)
                max_x = max(max_x, world_vert.x)
                max_y = max(max_y, world_vert.y)
                max_z = max(max_z, world_vert.z)

            # Clean up temporary mesh data
            eval_obj.to_mesh_clear()

    # Check if any curves or meshes were found
    if min_x == float("inf"):
        # Return None to indicate no valid objects found
        return None

    return (Vector((min_x, min_y, min_z)), Vector((max_x, max_y, max_z)))



def shift_scene_content(curve_collection, margin=0.2):
    """
    Shifts all scene objects (except the given curve collection) upward by the collection's height plus margin.
    
    Args:
        curve_collection: Collection containing curves to exclude from shifting
        margin: Additional vertical space to add above the curves (default: 0.4)
    """
    bounds = get_curve_collection_bounds(curve_collection)
    if bounds is None:
        print("No curves or meshes found in the collection to determine bounds.")
        return
    
    min_p, max_p = bounds
    dimensions = max_p - min_p
    
    # Select all objects except the curves in collection
    bpy.ops.object.select_all(action='SELECT')
    for obj in curve_collection.objects:
        obj.select_set(False)
    
    # Translate selected objects up
    bpy.ops.transform.translate(value=(0, dimensions.y + margin, 0))
    
    # Deselect all
    bpy.ops.object.select_all(action='DESELECT')