import os
import subprocess
import shutil
import sys
from pathlib import Path

# Import the generator script
# Ensure the current directory is in sys.path to allow import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import generate_sound_code

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_ROOT = os.path.join(BASE_DIR, "audio_input")
PROCESSED_ROOT = os.path.join(BASE_DIR, "audio_processed")
TARGET_ROOT = r"c:\Users\denis\Documents\GitHub\studyo_music_library\assets\sounds"

# FFmpeg settings
FFMPEG_BITRATE = "192k"  # High quality for mobile assets

def normalize_name(name):
    """Converts strings to snake_case style for filenames and folders."""
    clean = name.lower().strip().replace(" ", "_").replace("-", "_")
    return "".join(c for c in clean if c.isalnum() or c == "_")

def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        return False

def convert_to_m4a(input_path, output_path):
    """Converts input audio to m4a using ffmpeg."""
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-c:a", "aac",
        "-b:a", FFMPEG_BITRATE,
        "-vn",           # No video
        "-y",            # Overwrite
        "-loglevel", "error", # Quiet output
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error converting {input_path.name}: {e}")
        return False

def sync_to_library():
    """Copies processed files to the Flutter library assets."""
    print(f"\n[Sync] Syncing files from {PROCESSED_ROOT} to {TARGET_ROOT}...")
    
    if not os.path.exists(PROCESSED_ROOT):
        print(f"[Sync] Error: Processed directory not found!")
        return False

    try:
        # Use shutil.copytree with dirs_exist_ok=True (Python 3.8+)
        # This acts like a merge/overwrite
        shutil.copytree(PROCESSED_ROOT, TARGET_ROOT, dirs_exist_ok=True)
        print(f"[Sync] Sync completed successfully.")
        return True
    except Exception as e:
        print(f"[Sync] Error copying files: {e}")
        return False

def main():
    if not check_ffmpeg():
        print("Error: FFmpeg is not installed or not in system PATH.")
        return

    print("=" * 60)
    print("         STUDYO AUDIO PIPELINE")
    print("=" * 60)
    print(f"1. Convert Audio: {SOURCE_ROOT} -> {PROCESSED_ROOT}")
    print(f"2. Deploy Assets: {PROCESSED_ROOT} -> {TARGET_ROOT}")
    print(f"3. Generate Code: Updates sound_enums.dart & sound_paths.dart")
    print("-" * 60)

    # --- STEP 1: CONVERT AUDIO ---
    source_path = Path(SOURCE_ROOT)
    processed_path = Path(PROCESSED_ROOT)

    if not source_path.exists():
        print(f"Source directory not found: {source_path}")
        return

    processed_count = 0
    errors_count = 0

    for folder in source_path.iterdir():
        if not folder.is_dir():
            continue

        category_name = folder.name
        normalized_category = normalize_name(category_name)
        
        target_category_path = processed_path / normalized_category
        
        print(f"Processing Category: '{category_name}' -> '{normalized_category}'")
        
        if not target_category_path.exists():
            target_category_path.mkdir(parents=True, exist_ok=True)
            print(f"  [+] Created folder: {target_category_path}")

        for file_path in folder.iterdir():
            if file_path.is_file() and not file_path.name.startswith('.'):
                original_stem = file_path.stem
                normalized_filename = normalize_name(original_stem) + ".m4a"
                
                target_file_path = target_category_path / normalized_filename
                
                print(f"  Converting: {file_path.name} -> {normalized_filename} ... ", end="")
                
                success = convert_to_m4a(file_path, target_file_path)
                
                if success:
                    print("OK")
                    processed_count += 1
                else:
                    print("FAILED")
                    errors_count += 1

    print("-" * 60)
    print(f"Conversion Completed: {processed_count} processed, {errors_count} errors.")

    # --- STEP 2: SYNC TO LIBRARY ---
    if errors_count == 0:
        if sync_to_library():
             # --- STEP 3: GENERATE CODE ---
            print("-" * 60)
            print("[Generator] Running code generator...")
            generate_sound_code.generate_code()
        else:
            print("[Sync] Skipping code generation due to sync failure.")
    else:
        print("[Pipeline] Skipping Sync & Code Generation due to conversion errors.")
        print("Please resolve audio errors first.")

    print("\nAll tasks finished.")

if __name__ == "__main__":
    main()
