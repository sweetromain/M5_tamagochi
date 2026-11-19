# Script PlatformIO : régénère les sprites avant chaque compilation.
import os
import subprocess
import sys

Import("env")  # noqa: F821  (fourni par PlatformIO)

root = env.subst("$PROJECT_DIR")  # noqa: F821
tools = os.path.join(root, "tools")
try:
    import PIL  # noqa: F401
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])

ph = os.path.join(root, "assets", "placeholders")
if not os.path.isdir(ph):
    subprocess.check_call([sys.executable, os.path.join(tools, "make_placeholders.py")])
subprocess.check_call([sys.executable, os.path.join(tools, "png2rgb565.py")])
