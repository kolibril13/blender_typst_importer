# Blender Typst Importer

A Blender extension to render Typst files.
![thumbnail](https://github.com/user-attachments/assets/c9877b35-a0f3-4bbd-8de3-4a849292d0b3)

Tutorials:
Basics:
https://www.youtube.com/watch?v=w3FkHDPvp4o
How to Animate Algebra in Blender:
https://www.youtube.com/watch?v=IYveJn5M3TA

## Usage

1. **Prepare a Typst File**  
   Create a `.txt` file and write your Typst code in it. For more on Typst, check out https://github.com/typst/typst.

   Example Typst `hello.txt` code:

```typst
#set page(width: auto, height: auto, margin: 0cm, fill: none)
#set text(size: 50pt)
$ sum_(k=1)^n k = (n(n+1)) / 2 $
```


2. **Import the File into Blender**
   - Drag and drop `.txt` or `.typ` files directly into Blender.
   - Alternatively, go to **File -> Import -> Typst 🦢 via (.txt/.typ)**.



## API usage


```py
from typst_importer.typst_to_svg import typst_express
typst_express("$ a = b/c $")
```
![alt text](<docs/Clipboard 4. Feb 2025 at 18.39.jpeg>)



```py
from typst_importer.typst_to_svg import typst_express
content = "$ limits(integral)_a^b f(x) dif x $" 
typst_express(content, name="Integral Example")
```

![alt text](<docs/Clipboard 4. Feb 2025 at 18.58.jpeg>)




```py
typst_express("""
#let korange() = text(fill: orange)[$k$]
#let nblue() = text(fill: blue)[$n$]
$ sum_(#korange() = 1)^#nblue() #korange() = (nblue()(nblue()+1)) / 2 $  
""")
```
![alt text](<docs/Clipboard 4. Feb 2025 at 18.43.jpeg>)

````py
typst_express("""
#set page(width: 900pt, height: auto, margin: 0cm, fill: none)

#import "@preview/codelst:2.0.1": sourcecode
#import "@preview/tablex:0.0.8": tablex
#let sourcecode = sourcecode.with(frame: (code) => block(
  radius: 5pt,
  stroke: luma(30),
  inset: 30pt,
  text(size: 30pt, code)
))

#sourcecode[```python
for i in range(0,10):
  print(i)
```]
""")
````


![alt text](<docs/Clipboard 4. Feb 2025 at 18.44.jpeg>)





<!-- ### Equation as Greace Pencil Curve (still in development) -->


<!-- ### Equation as image (still in development) -->


# Changelog

## v0.1.14

- use latest typst-py version: https://github.com/messense/typst-py/tree/v0.13.2

## v0.1.13

- Better release workflow
- New tutorial


## v0.1.12

- Import every new curve as "n" instead of "Curve"
- new interface for animation in sthe side panel.
- Possible to align multiple collections at once.
- "Shift+F" to align objects

## v0.1.9,  v0.1.10, v0.1.11

- try new publishing workflow

## v0.1.8
- rename "my_opacity" to "opacity"
- Use an emission shader instead of principled bsdf, so that the text is not effected by scene light:
![image](https://github.com/user-attachments/assets/02049d1a-d659-4b66-8215-4415f433b2d7)


## v0.1.7

* Change blend_method for transparency. "Dithered" looks more grany, and the new default "Blended" looks smoother.

* update to typst 0.13.1
* 
* Added object indices support with blue numbered labels.

```py
from typst_importer.typst_to_svg import typst_express

content = "$ a = b + c $" 
c = typst_express(content, origin_to_char=True, show_indices=True, 
position=(0, 2, 0), name="Simple")
```


```py
content = "$ limits(integral)_a^b f(x) dif x $" 
c = typst_express(content, origin_to_char=True, show_indices=True, 
name="Integral")
```

![image](https://github.com/user-attachments/assets/60186484-a88d-4654-9346-d0f9b3ff9e57)


## v0.1.5

* update to typst 0.13.0
  
## v 0.1.4

* new position argument:

* add "Allign Object" operator.  Keyboard shortcut j, or  "Object -> Allign Object (XY)"
* add "Allign Collection". Keyboard shortcut l, or "Object -> Allign Collection (XY)" 

```py
typst_express(
    "hi",
    name="Example",
    position=(2, 2, 0),  # Place 2 units to the right
)
```
* Extra: Here's a snippet to position equation:
```py
from typst_importer.typst_to_svg import typst_express
def eq(equation: str, name: str, color: str, position=(0, 0, 0)):

    typst_code = f"""
    #set text({color})
    $ {equation} $
    """
    collection = typst_express(
        typst_code,
        origin_to_char=True,
        convert_to_mesh=True,
        name=name,
        position=position
    )

    return collection


eq("a -b = c", "Start", "aqua", (0, -4, 0.5))
eq("a - 3 r_(beta) = c", "End", "olive", (0, -4, 0));
```



## v 0.1.3

added `lxml` dependency

## v 0.1.2

* new function: convert from curve to mesh : `convert_to_mesh`
```py
c = typst_express("$ . . . $", scale_factor=100, origin_to_char=False, convert_to_mesh=True)
```
* Better handeling of materials. (see https://projects.blender.org/blender/blender/issues/134451)
* Every element has now a default "opacity" property



## v 0.1.1

* add new function: `c.processed_svg`
```py
from typst_importer.typst_to_svg import typst_express
from typst_importer.notebook_utils import display_svg
c = typst_express("""
#set math.lr(size: 80%)
$ integral.triple _V (nabla dot accent(F, arrow)) dif V = integral.surf_(partial V)  (accent(F, arrow) dot accent(n, arrow)) dif A $
"""
)
display_svg(c.processed_svg, width="400px")
```


* New docs at: https://kolibril13.github.io/bpy-gallery/n2typst_examples/

* new thumbnail

## v 0.1.0
### New Features
* Added customizable scaling and positioning options to `typst_express`:
  - `scale_factor`: Control the size of the rendered output (default: 100.0)
  - `origin_to_char`: Option to adjust origin point relative to characters (default: False)
```py
def typst_express(
    content: str,
    name: str = "typst_expr",
    header: str = "",
    scale_factor: float = 100.0,
    origin_to_char: bool = False
)
```

For example
```py
from typst_importer.typst_to_svg import typst_express
typst_express("$ a = b/d $" , scale_factor=200, origin_to_char=True)
```
![alt text](<docs/Clipboard 5. Feb 2025 at 15.23.jpeg>)


* `get_curve_collection_bounds` will get the deminsons of a collection, e.g. 
```py
from typst_importer.typst_to_svg import typst_express
from typst_importer.curve_utils import get_curve_collection_bounds
c = typst_express("$ a = b/d$", scale_factor=100, origin_to_char=False)
min_p, max_p = get_curve_collection_bounds(c)
print(min_p, max_p)
# out <Vector (0.0249, -0.2190, 0.0000)> <Vector (1.4839, 0.5474, 0.0000)>
```
* `shift_scene_content` will shift all scene_content to a new position except the given collection c.
```py
from typst_importer.typst_to_svg import typst_express
from typst_importer.curve_utils import shift_scene_content

c = typst_express("$ a = b/d$", scale_factor=100, origin_to_char=False)
shift_scene_content(c)  

```
### Improvements
* Enhanced SVG preprocessing pipeline:
  - `flatten_svg` will flatten the SVG structure fist
  - `stroke_to_filled_path` will convert all strokes to paths.

Before <-> After:

![alt text](tests/comparison.jpeg)

```py
from typst_importer.svg_preprocessing import  flatten_svg, stroke_to_filled_path
svg_content = open("test.svg").read()
svg_content = flatten_svg(svg_content)
svg_content = stroke_to_filled_path(svg_content)

open("test_filled.svg", "w").write(svg_content)
```
or combined as `preprocess_svg`
```py
from typst_importer.svg_preprocessing import preprocess_svg
svg_content = open("test.svg").read()
svg_content = preprocess_svg(svg_content)
open("test_filled.svg", "w").write(svg_content)
```

### Developer Tools
* Added new notebook utilities for easier development and testing:
  - `display_svg` function to display svgs in Jupyter.

```py
from typst_importer.notebook_utils import display_svg
display_svg(step1_content , width='500px')
```


### Documentation
* Added examples for new features
## v 0.0.7

* fix problem with vertical strokes
* new thumbnail
* Apply all transformations
* new helper function `from typst_importer.curve_utils import get_curve_collection_bounds` in order to transform equations.
* new function `from typst_importer.curve_utils import shift_scene_content`
  
## v 0.0.6 

* `from typst_importer.typst_to_svg import typst_express`
* `from typst_importer.typst_to_svg import typst_to_blender_curves` 
* Improved support for code blocks, addressing issues in the SVG algorithm
* Enhanced documentation
* Experimentation with Greace Pencil Curve
* Debugging notebook


## v 0.0.5
* add support for both .typ and .txt
* Add Color support for Typst Equations (https://github.com/kolibril13/blender_typst_importer/pull/2)
* Better handeling for strokes, e.g. in an equation like a/b.


## v 0.0.4 
* better packaging

## v 0.0.3 

* Add Drag'n drop support
