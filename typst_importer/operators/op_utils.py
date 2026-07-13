import bpy


def get_or_create_collection(name):
    """Get a collection by name, or create it if it doesn't exist"""
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    else:
        # Create new collection
        collection = bpy.data.collections.new(name)
        # Link it to the scene
        bpy.context.scene.collection.children.link(collection)
        return collection


def animation_fcurves(obj: bpy.types.Object):
    """Return the object's active Action f-curves across Blender action APIs."""
    if obj.animation_data is None or obj.animation_data.action is None:
        return ()

    action = obj.animation_data.action
    if hasattr(action, "fcurves"):
        return action.fcurves

    slot = obj.animation_data.action_slot
    if slot is None:
        return ()

    for layer in action.layers:
        for strip in layer.strips:
            channelbag = strip.channelbag(slot)
            if channelbag is not None:
                return channelbag.fcurves
    return ()
