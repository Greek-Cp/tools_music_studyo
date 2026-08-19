import os

# Default: folder sibling dari repo tools ini. Override dengan env STUDYO_MUSIC_LIBRARY.
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
LIBRARY_ROOT = os.environ.get(
    "STUDYO_MUSIC_LIBRARY",
    os.path.join(os.path.dirname(TOOLS_DIR), "studyo_music_library"),
)
PUBSPEC_FILE = os.path.join(LIBRARY_ROOT, "pubspec.yaml")

def check_specific():
    with open(PUBSPEC_FILE, 'r') as f:
        content = f.read()
    
    cats = ['bump_hit', 'coin_win', 'countdown', 'finish', 'speed_up']
    print(f"Checking specific categories in pubspec content ({len(content)} chars)...")
    
    for cat in cats:
        path = f"assets/sounds/{cat}/"
        found = path in content
        print(f"  {cat}: {'FOUND' if found else 'MISSING'}")

if __name__ == "__main__":
    check_specific()
