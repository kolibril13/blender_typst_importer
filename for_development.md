import subprocess
import sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "typst", "databpy" ,"svg.path" , "lxml"])


from importlib.metadata import version
version("databpy")
version("typst")