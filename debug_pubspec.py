import os

# Default: folder sibling dari repo tools ini. Override dengan env STUDYO_MUSIC_LIBRARY.
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
LIBRARY_ROOT = os.environ.get(
    "STUDYO_MUSIC_LIBRARY",
    os.path.join(os.path.dirname(TOOLS_DIR), "studyo_music_library"),
)
PUBSPEC_FILE = os.path.join(LIBRARY_ROOT, "pubspec.yaml")
ASSETS_DIR = os.path.join(LIBRARY_ROOT, "assets", "sounds")

def debug_update_pubspec():
    if not os.path.exists(PUBSPEC_FILE):
        print("Pubspec not found")
        return

    # Mock categories present in dirs
    categories = [d for d in os.listdir(ASSETS_DIR) if os.path.isdir(os.path.join(ASSETS_DIR, d))]
    print(f"Categories found in dir: {categories}")

    with open(PUBSPEC_FILE, 'r') as f:
        lines = f.readlines()
        
    existing_assets = set()
    assets_section_found = False
    flutter_found = False
    
    for line in lines:
        stripped = line.strip()
        if stripped == 'flutter:':
            flutter_found = True
        elif stripped == 'assets:' and flutter_found:
            assets_section_found = True
        elif assets_section_found:
            if not line.startswith('  ') and stripped != '':
                 assets_section_found = False
            else:
                if stripped.startswith('- assets/sounds/'):
                     # assets/sounds/background/ -> background
                     path = stripped.replace('-', '').strip().strip('/') # assets/sounds/background
                     cat = os.path.basename(path)
                     existing_assets.add(cat)
                     
    print(f"Existing assets in pubspec: {existing_assets}")
    
    missing = [c for c in categories if c not in existing_assets]
    print(f"MISSING: {missing}")

if __name__ == "__main__":
    debug_update_pubspec()
