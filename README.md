# Blender Typst Importer

A Blender extension to render Typst files.
![thumbnail](https://github.com/user-attachments/assets/c9877b35-a0f3-4bbd-8de3-4a849292d0b3)

## Tutorials:
* Basics:  
https://www.youtube.com/watch?v=w3FkHDPvp4o

* How to Animate Algebra in Blender:  
https://www.youtube.com/watch?v=IYveJn5M3TA

## Usage

![shapes at 25-11-18 14 03 14](https://github.com/user-attachments/assets/00f1a3df-f9a7-4f79-91ad-d1961148981f)

![shapes at 25-11-18 14 03 25](https://github.com/user-attachments/assets/0112e508-4a84-4a28-a441-325f2059270f)

![shapes at 25-11-18 14 03 39](https://github.com/user-attachments/assets/3584e624-873d-4926-a77d-4bbb94f27114)

# Python API

```py
from bl_ext.blender_org.typst_importer.typst_to_svg import typst_express
typst_express("$ a = b/c $")
```

Import as native Blender 5.2 Grease Pencil objects:

```py
typst_express("$ a = b/c $", use_grease_pencil=True)
```

Every imported Grease Pencil glyph gets a shared **Typst Stroke Radius**
Geometry Nodes group. Adjust **Stroke Radius** in the modifier (the default is
`0.01`), or choose the initial radius from Python:

```py
typst_express(
    "$ a = b/c $",
    use_grease_pencil=True,
    grease_pencil_stroke_radius=0.02,
)
```

The Typst color remains the fill color and the generated stroke is black.

More python examples at:
https://kolibril13.github.io/bpy-gallery/n4typst_examples/
