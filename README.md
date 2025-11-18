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
