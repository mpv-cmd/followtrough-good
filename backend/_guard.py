import pathlib
import sys

HERE = pathlib.Path(__file__).resolve()
BACKEND_DIR = HERE.parent

BAD_MARKERS = [
    "<html",
    "<!doctype",
    "<body",
    "<head",
    "</html",
    "__pycache__/",
    ".gitignore",
    "node_modules",
]

for py in BACKEND_DIR.glob("*.py"):
    if py.resolve() == HERE:
        continue

    txt = py.read_text(errors="ignore").lower()

    for bad in BAD_MARKERS:
        if bad in txt:
            print(f"❌ BACKEND CORRUPTION DETECTED")
            print(f"File: {py.name}")
            print(f"Marker: {bad}")
            print("Backend files must contain ONLY Python code.")
            sys.exit(1)