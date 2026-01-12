import os

PUBSPEC_FILE = r"c:\Users\denis\Documents\GitHub\studyo_music_library\pubspec.yaml"

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
