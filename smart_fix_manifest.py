import json
import os
from datetime import datetime, timedelta

# Konfigurasi Path
ASSETS_DIR = r"c:\Users\denis\Documents\GitHub\studyo_music_library\assets\sounds"
MANIFEST_FILE = os.path.join(ASSETS_DIR, "sound_manifest.json")

def smart_fix_manifest():
    if not os.path.exists(MANIFEST_FILE):
        print("Manifest file not found!")
        return

    # Load Manifest
    try:
        with open(MANIFEST_FILE, 'r') as f:
            manifest = json.load(f)
    except:
        manifest = {}

    print(f"Scanning physical files in: {ASSETS_DIR}")
    
    updates_count = 0
    now = datetime.now()
    
    # 24 Hours Threshold
    threshold_hours = 24 

    # Scan Categories
    categories = [d for d in os.listdir(ASSETS_DIR) if os.path.isdir(os.path.join(ASSETS_DIR, d))]
    
    for category in categories:
        cat_path = os.path.join(ASSETS_DIR, category)
        files = [f for f in os.listdir(cat_path) if f.lower().endswith('.m4a')]
        
        for file in files:
            full_path = os.path.join(cat_path, file)
            rel_path = f"{category}/{file}"
            
            # Get OS File Creation/Modification Time
            stats = os.stat(full_path)
            # Use mtime (modification time) as likely proxy for "when it was put here"
            mod_time = datetime.fromtimestamp(stats.st_mtime)
            
            # Check difference
            diff = now - mod_time
            
            # If changed/created in last 24 hours -> Update Manifest to NOW/ModTime
            # (Unless user specifically wants strictly "new to manifest". But here we want to restore "New" status)
            if diff < timedelta(hours=threshold_hours):
                print(f"  [RESTORE NEW] {rel_path} (Modified {diff.seconds//3600}h {(diff.seconds//60)%60}m ago)")
                manifest[rel_path] = mod_time.isoformat()
                updates_count += 1
            else:
                # Ensure it remains 'old' if it is physically old
                # We can leave it as is (which might be 2024 from previous fix)
                pass

    if updates_count > 0:
        print(f"\nUpdating manifest with {updates_count} recent files...")
        with open(MANIFEST_FILE, 'w') as f:
            json.dump(manifest, f, indent=2)
        print("Success. Please run generator to apply.")
    else:
        print("\nNo recent files found (last 24h). No updates made.")

if __name__ == "__main__":
    smart_fix_manifest()
