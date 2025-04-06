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