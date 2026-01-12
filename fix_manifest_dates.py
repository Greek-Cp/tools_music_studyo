import json
import os
from datetime import datetime

# Path ke manifest
MANIFEST_FILE = r"c:\Users\denis\Documents\GitHub\studyo_music_library\assets\sounds\sound_manifest.json"

def fix_manifest():
    if not os.path.exists(MANIFEST_FILE):
        print("Manifest file not found!")
        return

    try:
        with open(MANIFEST_FILE, 'r') as f:
            manifest = json.load(f)
        
        print(f"Loaded {len(manifest)} entries.")
        
        # Set date to past (Old Asset)
        old_date = "2024-01-01T00:00:00.000000"
        
        count = 0
        for key in manifest:
            manifest[key] = old_date
            count += 1
            
        with open(MANIFEST_FILE, 'w') as f:
            json.dump(manifest, f, indent=2)
            
        print(f"Success! Reset {count} assets to 'Old Date' ({old_date}).")
        print("Please run process_audio.py or generate_sound_code.py again to update dart files.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_manifest()
