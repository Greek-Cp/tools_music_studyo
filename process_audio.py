import os
import json
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
# Root project studyo_music_library (samakan dengan generate_sound_code.py)
LIBRARY_ROOT = generate_sound_code.LIBRARY_ROOT
TARGET_ROOT = os.path.join(LIBRARY_ROOT, "assets", "sounds")

# --- FFmpeg / encoding settings ---
#
# Target bitrate untuk sumber lossless (wav/flac/aiff).
# 128k AAC-LC sudah transparan untuk SFX/ambience di speaker mobile.
LOSSLESS_TARGET_KBPS = 128

# Untuk sumber yang SUDAH lossy (m4a/mp3/ogg): re-encode di bitrate yang sama
# atau lebih tinggi justru MEMBESARKAN file tanpa menambah kualitas (generation
# loss). Kita hanya re-encode kalau bisa hemat minimal MIN_SAVING_PCT persen,
# dengan cara turun ke bitrate di bawah bitrate sumber.
LOSSY_HEADROOM = 0.75   # target = 75% dari bitrate sumber
LOSSY_FLOOR_KBPS = 96   # jangan turun di bawah ini (jaga kejernihan)
MIN_SAVING_PCT = 10     # kalau hemat < 10%, stream-copy saja

# Batas bawah/atas bitrate hasil
MIN_KBPS = 64
MAX_KBPS = 256

# Ekstensi sumber lossless
LOSSLESS_EXTS = {".wav", ".flac", ".aiff", ".aif", ".alac", ".pcm"}

# Encoder AAC. aac_at (AudioToolbox, native macOS) kualitasnya lebih baik
# daripada encoder "aac" bawaan FFmpeg pada bitrate rendah.
_AAC_ENCODER = None


def get_aac_encoder():
    """Pilih encoder AAC terbaik yang tersedia (aac_at di macOS, fallback aac)."""
    global _AAC_ENCODER
    if _AAC_ENCODER is None:
        try:
            out = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True, text=True, check=False,
            ).stdout
            _AAC_ENCODER = "aac_at" if " aac_at " in out else "aac"
        except Exception:
            _AAC_ENCODER = "aac"
    return _AAC_ENCODER


def probe_audio(path):
    """Ambil metadata audio: codec, bitrate (kbps), channels, durasi, ukuran."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,bit_rate,channels,sample_rate",
        "-show_entries", "format=duration,bit_rate,size",
        "-of", "json", str(path),
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        data = json.loads(out)
    except Exception:
        return None

    streams = data.get("streams") or [{}]
    stream = streams[0]
    fmt = data.get("format") or {}

    def as_int(value):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    size = as_int(fmt.get("size"))
    duration = float(fmt.get("duration") or 0) or 0.0

    # Bitrate stream lebih akurat; fallback ke format, lalu hitung dari ukuran.
    bitrate = as_int(stream.get("bit_rate")) or as_int(fmt.get("bit_rate"))
    if not bitrate and duration > 0 and size:
        bitrate = int(size * 8 / duration)

    return {
        "codec": stream.get("codec_name") or "",
        "kbps": bitrate // 1000 if bitrate else 0,
        "channels": as_int(stream.get("channels")) or 2,
        "sample_rate": as_int(stream.get("sample_rate")),
        "duration": duration,
        "size": size,
    }


def plan_encode(input_path, info):
    """
    Tentukan strategi encoding.

    Return (action, kbps, reason):
      action "encode" -> transcode ke AAC pada `kbps`
      action "copy"   -> stream-copy (remux) tanpa re-encode
    """
    ext = Path(input_path).suffix.lower()
    is_lossless = ext in LOSSLESS_EXTS or (info or {}).get("codec", "").startswith("pcm")

    if info is None:
        return "encode", LOSSLESS_TARGET_KBPS, "probe gagal, pakai default"

    src_kbps = info["kbps"]

    if is_lossless:
        return "encode", LOSSLESS_TARGET_KBPS, f"lossless {src_kbps}k -> AAC"

    # Sumber sudah lossy.
    if src_kbps <= 0:
        return "encode", LOSSLESS_TARGET_KBPS, "bitrate sumber tak terbaca"

    # Sudah cukup kecil? jangan disentuh, re-encode hanya menurunkan kualitas.
    if src_kbps <= LOSSY_FLOOR_KBPS:
        return "copy", src_kbps, f"sumber {src_kbps}k sudah <= {LOSSY_FLOOR_KBPS}k"

    target = max(LOSSY_FLOOR_KBPS, int(src_kbps * LOSSY_HEADROOM))
    target = max(MIN_KBPS, min(MAX_KBPS, target))

    saving = (src_kbps - target) * 100.0 / src_kbps
    if saving < MIN_SAVING_PCT:
        return "copy", src_kbps, f"hemat hanya {saving:.0f}%, tidak sepadan"

    return "encode", target, f"lossy {src_kbps}k -> {target}k (hemat ~{saving:.0f}%)"

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
    """
    Konversi audio ke m4a dengan strategi adaptif.

    Kunci: file yang sudah lossy (m4a/mp3) TIDAK di-re-encode ke bitrate lebih
    tinggi, karena itu hanya membesarkan ukuran tanpa menambah kualitas.
    """
    info = probe_audio(input_path)
    action, kbps, reason = plan_encode(input_path, info)

    base = ["ffmpeg", "-i", str(input_path), "-vn", "-y", "-loglevel", "error"]

    if action == "copy":
        # Remux tanpa re-encode: kualitas 100% identik, tanpa generation loss.
        cmd = base + ["-c:a", "copy", "-movflags", "+faststart", str(output_path)]
    else:
        cmd = base + [
            "-c:a", get_aac_encoder(),
            "-b:a", f"{kbps}k",
            "-movflags", "+faststart",
            str(output_path),
        ]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        # Stream-copy bisa gagal kalau codec sumber tidak cocok untuk container
        # m4a (mis. mp3/vorbis). Fallback: encode ke AAC.
        if action == "copy":
            fallback_kbps = max(MIN_KBPS, min(MAX_KBPS, kbps or LOSSLESS_TARGET_KBPS))
            cmd = base + [
                "-c:a", get_aac_encoder(),
                "-b:a", f"{fallback_kbps}k",
                "-movflags", "+faststart",
                str(output_path),
            ]
            try:
                subprocess.run(cmd, check=True)
                action, kbps = "encode", fallback_kbps
                reason = "stream-copy gagal, fallback encode"
            except subprocess.CalledProcessError as e:
                print(f"Error converting {Path(input_path).name}: {e}")
                return None
        else:
            print(f"Error converting {Path(input_path).name}: {e}")
            return None

    src_size = (info or {}).get("size") or os.path.getsize(input_path)
    out_size = os.path.getsize(output_path)

    # Safety net: kalau hasil malah lebih besar dari sumber, pakai sumber apa
    # adanya (kalau sudah m4a) supaya asset tidak pernah membengkak.
    if out_size > src_size and Path(input_path).suffix.lower() == ".m4a":
        shutil.copy2(input_path, output_path)
        out_size = os.path.getsize(output_path)
        action, reason = "copy", "hasil encode lebih besar, pakai sumber asli"

    return {
        "action": action,
        "kbps": kbps,
        "reason": reason,
        "src_size": src_size,
        "out_size": out_size,
    }

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
    print(f"Encoder: {get_aac_encoder()}  |  lossless target: {LOSSLESS_TARGET_KBPS}k  |  lossy floor: {LOSSY_FLOOR_KBPS}k")
    print("-" * 60)
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
    total_src_bytes = 0
    total_out_bytes = 0

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
                
                print(f"  {file_path.name} -> {normalized_filename} ... ", end="", flush=True)

                result = convert_to_m4a(file_path, target_file_path)

                if result:
                    src_mb = result["src_size"] / 1048576
                    out_mb = result["out_size"] / 1048576
                    delta = (
                        (result["out_size"] - result["src_size"]) * 100.0 / result["src_size"]
                        if result["src_size"] else 0.0
                    )
                    tag = "copy" if result["action"] == "copy" else f'{result["kbps"]}k'
                    print(f"OK [{tag}] {src_mb:.2f}MB -> {out_mb:.2f}MB ({delta:+.0f}%)")
                    total_src_bytes += result["src_size"]
                    total_out_bytes += result["out_size"]
                    processed_count += 1
                else:
                    print("FAILED")
                    errors_count += 1

    print("-" * 60)
    print(f"Conversion Completed: {processed_count} processed, {errors_count} errors.")
    if total_src_bytes:
        saved = total_src_bytes - total_out_bytes
        print(
            f"Total size: {total_src_bytes / 1048576:.2f}MB -> "
            f"{total_out_bytes / 1048576:.2f}MB "
            f"(saved {saved / 1048576:.2f}MB, {saved * 100.0 / total_src_bytes:.1f}%)"
        )

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
