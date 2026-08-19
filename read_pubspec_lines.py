import os

# Default: folder sibling dari repo tools ini. Override dengan env STUDYO_MUSIC_LIBRARY.
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
LIBRARY_ROOT = os.environ.get(
    "STUDYO_MUSIC_LIBRARY",
    os.path.join(os.path.dirname(TOOLS_DIR), "studyo_music_library"),
)
filename = os.path.join(LIBRARY_ROOT, "pubspec.yaml")
with open(filename, 'r') as f:
    for i, line in enumerate(f):
        if "assets/sounds/" in line:
            print(f"{i+1}: {line.rstrip()}")
