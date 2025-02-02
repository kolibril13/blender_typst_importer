# Blender Typst Importer

A Blender extension to render Typst files.

## Usage

1. **Prepare a Typst File**  
   Create a `.txt` file and write your Typst code in it. For more on Typst, check out https://github.com/typst/typst.

   Example Typst `hello.txt` code:

```typst
#set page(width: auto, height: auto, margin: 0cm, fill: none)
#set text(size: 5000pt)
$ sum_(k=1)^n k = (n(n+1)) / 2 $
```

And here's an example using colored equations:
```typst
#set page(width: auto, height: auto, margin: 0cm, fill: none)
#set text(size: 5000pt)

#let korange() = text(fill: orange)[$k$]
#let nblue() = text(fill: blue)[$n$]

$ sum_(#korange() = 1)^#nblue() #korange() = (nblue()(nblue()+1)) / 2 $  
 ```

## API usage
### Equation as SVG Curve

```py
from pathlib import Path
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
col = bpy.context.scene.collection.children['hello.svg']
col.name = "Formula"
```
![alt text](<Clipboard 2. Feb 2025 at 22.05.jpeg>)
### Equation as Greace Pencil Curve

### Equation as image
```py

```


2. **Import the File into Blender**
   - Drag and drop `.txt` or `.typ` files directly into Blender.
   - Alternatively, go to **File -> Import -> Typst 🦢 via (.txt/.typ)**.

# Changelog

## v 0.0.5
* add support for both .typ and .txt
* Add Color support for Typst Equations (https://github.com/kolibril13/blender_typst_importer/pull/2)
* Better handeling for strokes, e.g. in an equation like a/b.


v 0.0.4 better packaging

v 0.0.3 Add Drag'n drop support
