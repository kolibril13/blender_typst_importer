# Blender Typst Importer

A Blender extension to render Typst files.

## Usage

1. **Prepare a Typst File**  
   Create a `.txt` file and write your Typst code in it. For more on Typst, check out https://github.com/typst/typst.

   Example Typst "hello.txt" code:

   ```typst
   #set page(width: auto, height: auto, margin: 0cm, fill: none)
   #set text(size: 5000pt)
   $ sum_(k=1)^n k = (n(n+1)) / 2 $
   ```

2. **Import the File into Blender**
   - Drag and drop the `.txt` file directly into Blender.
   - Alternatively, go to **File -> Import -> Typst (.txt)**.

# Changelog

v 0.0.3 Add Drag'n drop support
