#!/usr/bin/env python3
"""
compress_audio.py - Kompresi audio, fokus hemat ukuran tanpa kehilangan kejernihan.

Developer cukup atur SOURCE_DIR (atau lewat argumen CLI). Script akan:
  1. Scan semua file audio di dalam folder tersebut, termasuk subfolder.
  2. Kompres tiap file dengan bitrate adaptif.
  3. Simpan hasil ke <SOURCE_DIR>/result_compress/ dengan struktur folder
     yang PERSIS sama seperti sumbernya.

Contoh:
    sound/
      bgm/forest.wav          ->  sound/result_compress/bgm/forest.m4a
      sfx/ui/click.m4a        ->  sound/result_compress/sfx/ui/click.m4a
      intro.mp3               ->  sound/result_compress/intro.m4a

Cara pakai:
    python3 compress_audio.py                    # pakai SOURCE_DIR di bawah
    python3 compress_audio.py sound/             # tentukan folder lain
    python3 compress_audio.py sound/ --dry-run   # lihat rencana, tanpa menulis
    python3 compress_audio.py sound/ --bitrate 96
    python3 compress_audio.py sound/ --mono -b 64   # mono, cocok untuk SFX

Catatan: ukuran file ditentukan oleh BITRATE, bukan jumlah channel. Jadi
--mono saja tidak mengecilkan file; gunakan bersama -b yang lebih rendah.
Untungnya, pada bitrate sama mono terdengar lebih bersih daripada stereo.

Butuh: ffmpeg & ffprobe terpasang di PATH.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# KONFIGURASI - developer cukup ubah bagian ini
# ---------------------------------------------------------------------------

# Folder sumber yang ingin dikompres. Boleh absolut atau relatif terhadap
# lokasi script ini. Bisa ditimpa lewat argumen CLI.
SOURCE_DIR = "sound"

# Nama folder output di dalam SOURCE_DIR.
RESULT_DIRNAME = "result_compress"

# Target bitrate (kbps) untuk sumber lossless (wav/flac/aiff).
LOSSLESS_TARGET_KBPS = 128

# Untuk sumber yang SUDAH lossy (m4a/mp3/ogg): re-encode ke bitrate sama atau
# lebih tinggi hanya MEMBESARKAN file tanpa menambah kualitas. Jadi kita turun
# ke sebagian bitrate sumber, dan berhenti di lantai tertentu.
LOSSY_HEADROOM = 0.75   # target = 75% dari bitrate sumber
LOSSY_FLOOR_KBPS = 96   # jangan turun di bawah ini
MIN_SAVING_PCT = 10     # hemat < 10% dianggap tidak sepadan -> stream-copy

# Batas aman bitrate hasil.
MIN_KBPS = 64
MAX_KBPS = 256

# ---------------------------------------------------------------------------

AUDIO_EXTS = {
    ".wav", ".flac", ".aiff", ".aif", ".alac",
    ".m4a", ".mp3", ".aac", ".ogg", ".oga", ".opus", ".wma",
}
LOSSLESS_EXTS = {".wav", ".flac", ".aiff", ".aif", ".alac", ".pcm"}

_AAC_ENCODER = None


def human(num_bytes):
    """Format ukuran byte jadi string yang mudah dibaca."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}B"
        size /= 1024
    return f"{size:.1f}GB"


def check_tools():
    """Pastikan ffmpeg & ffprobe tersedia."""
    missing = [t for t in ("ffmpeg", "ffprobe") if shutil.which(t) is None]
    if missing:
        print(f"Error: {', '.join(missing)} tidak ditemukan di PATH.")
        print("Install dulu, contoh di macOS: brew install ffmpeg")
        return False
    return True


def get_aac_encoder():
    """Pilih encoder AAC terbaik: aac_at (macOS) lebih bagus di bitrate rendah."""
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
    """Baca metadata audio: codec, bitrate (kbps), channels, durasi, ukuran."""
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

    streams = data.get("streams") or []
    if not streams:
        return None  # tidak ada stream audio
    stream = streams[0]
    fmt = data.get("format") or {}

    def as_int(value):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    size = as_int(fmt.get("size")) or os.path.getsize(path)
    duration = float(fmt.get("duration") or 0) or 0.0

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


def plan_encode(input_path, info, target_kbps=None):
    """
    Tentukan strategi kompresi.

    Return (action, kbps, reason):
      "encode" -> transcode ke AAC pada `kbps`
      "copy"   -> stream-copy, tanpa re-encode (kualitas identik)
    """
    ext = Path(input_path).suffix.lower()
    is_lossless = ext in LOSSLESS_EXTS or (info or {}).get("codec", "").startswith("pcm")

    if info is None:
        return "encode", target_kbps or LOSSLESS_TARGET_KBPS, "probe gagal, pakai default"

    src_kbps = info["kbps"]

    if is_lossless:
        kbps = target_kbps or LOSSLESS_TARGET_KBPS
        return "encode", kbps, f"lossless {src_kbps}k -> {kbps}k"

    # Sumber sudah lossy.
    if src_kbps <= 0:
        kbps = target_kbps or LOSSLESS_TARGET_KBPS
        return "encode", kbps, "bitrate sumber tak terbaca"

    if target_kbps:
        # Developer minta bitrate spesifik. Hormati, tapi jangan naikkan.
        if target_kbps >= src_kbps:
            return "copy", src_kbps, f"sumber {src_kbps}k <= target {target_kbps}k"
        return "encode", target_kbps, f"lossy {src_kbps}k -> {target_kbps}k"

    if src_kbps <= LOSSY_FLOOR_KBPS:
        return "copy", src_kbps, f"sumber {src_kbps}k sudah <= {LOSSY_FLOOR_KBPS}k"

    kbps = max(LOSSY_FLOOR_KBPS, int(src_kbps * LOSSY_HEADROOM))
    kbps = max(MIN_KBPS, min(MAX_KBPS, kbps))

    saving = (src_kbps - kbps) * 100.0 / src_kbps
    if saving < MIN_SAVING_PCT:
        return "copy", src_kbps, f"hemat cuma {saving:.0f}%, tidak sepadan"

    return "encode", kbps, f"lossy {src_kbps}k -> {kbps}k"


def compress_file(input_path, output_path, target_kbps=None, force_mono=False):
    """Kompres satu file. Return dict hasil, atau None kalau gagal."""
    info = probe_audio(input_path)
    action, kbps, reason = plan_encode(input_path, info, target_kbps)

    # Mono butuh re-encode, stream-copy tidak bisa mengubah jumlah channel.
    if force_mono and action == "copy" and (info or {}).get("channels", 1) > 1:
        action = "encode"
        kbps = kbps or LOSSLESS_TARGET_KBPS
        reason += " + downmix mono"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    base = ["ffmpeg", "-i", str(input_path), "-vn", "-y", "-loglevel", "error"]
    tail = ["-movflags", "+faststart", str(output_path)]

    if action == "copy":
        cmd = base + ["-c:a", "copy"] + tail
    else:
        cmd = base + ["-c:a", get_aac_encoder(), "-b:a", f"{kbps}k"]
        if force_mono:
            cmd += ["-ac", "1"]
        cmd += tail

    def run(command):
        """Jalankan ffmpeg, tangkap stderr supaya output tetap rapi."""
        return subprocess.run(command, capture_output=True, text=True)

    proc = run(cmd)
    if proc.returncode != 0:
        # Stream-copy bisa gagal kalau codec sumber tak cocok untuk container
        # m4a (mis. mp3/vorbis). Fallback ke encode AAC.
        if action == "copy":
            fallback = max(MIN_KBPS, min(MAX_KBPS, kbps or LOSSLESS_TARGET_KBPS))
            cmd = base + ["-c:a", get_aac_encoder(), "-b:a", f"{fallback}k"]
            if force_mono:
                cmd += ["-ac", "1"]
            cmd += tail
            proc = run(cmd)
            if proc.returncode == 0:
                action, kbps = "encode", fallback
                reason = "stream-copy gagal, fallback encode"

        if proc.returncode != 0:
            # Ambil baris error terakhir yang bermakna saja.
            lines = [ln.strip() for ln in (proc.stderr or "").splitlines() if ln.strip()]
            detail = lines[-1] if lines else "ffmpeg gagal"
            # Jangan tinggalkan file setengah jadi.
            if output_path.exists():
                output_path.unlink()
            return {"error": detail}

    src_size = (info or {}).get("size") or os.path.getsize(input_path)
    out_size = os.path.getsize(output_path)

    # Jaring pengaman: hasil tidak boleh lebih besar dari sumber.
    if out_size > src_size and not force_mono:
        if Path(input_path).suffix.lower() == ".m4a":
            shutil.copy2(input_path, output_path)
            out_size = os.path.getsize(output_path)
            action, reason = "copy", "hasil lebih besar, pakai sumber asli"

    return {
        "action": action,
        "kbps": kbps,
        "reason": reason,
        "src_size": src_size,
        "out_size": out_size,
    }


def scan_audio_files(source_dir, result_dir):
    """Kumpulkan semua file audio, kecuali yang ada di folder hasil."""
    files = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in AUDIO_EXTS:
            continue
        # Jangan proses ulang isi folder hasil.
        if result_dir == path or result_dir in path.parents:
            continue
        files.append(path)
    return files


def main():
    parser = argparse.ArgumentParser(
        description="Kompres semua audio dalam sebuah folder, struktur folder dipertahankan.",
    )
    parser.add_argument(
        "source", nargs="?", default=None,
        help=f"Folder sumber audio (default: {SOURCE_DIR})",
    )
    parser.add_argument(
        "-b", "--bitrate", type=int, default=None, metavar="KBPS",
        help="Paksa bitrate target, mis. 96. Default: adaptif per file.",
    )
    parser.add_argument(
        "--mono", action="store_true",
        help="Downmix ke mono. Ukuran ditentukan bitrate, jadi mono TIDAK "
             "otomatis mengecilkan file - gabungkan dengan -b yang lebih "
             "rendah (mis. --mono -b 64) untuk hemat nyata dengan kualitas "
             "per-bit yang lebih baik.",
    )
    parser.add_argument(
        "-n", "--dry-run", action="store_true",
        help="Tampilkan rencana saja, tidak menulis file apa pun.",
    )
    args = parser.parse_args()

    if not check_tools():
        return 1

    script_dir = Path(__file__).resolve().parent
    raw_source = args.source or SOURCE_DIR
    source_dir = Path(raw_source).expanduser()
    if not source_dir.is_absolute():
        # Coba relatif terhadap cwd dulu, lalu relatif terhadap lokasi script.
        candidate = Path.cwd() / source_dir
        source_dir = candidate if candidate.exists() else script_dir / source_dir
    source_dir = source_dir.resolve()

    if not source_dir.is_dir():
        print(f"Error: folder sumber tidak ditemukan: {source_dir}")
        print("Atur SOURCE_DIR di script, atau berikan path lewat argumen.")
        return 1

    result_dir = source_dir / RESULT_DIRNAME

    print("=" * 68)
    print("            KOMPRESI AUDIO")
    print("=" * 68)
    print(f"Sumber  : {source_dir}")
    print(f"Hasil   : {result_dir}")
    encoder = get_aac_encoder()
    mode = f"{args.bitrate}k (dipaksa)" if args.bitrate else "adaptif per file"
    print(f"Encoder : {encoder}  |  bitrate: {mode}  |  mono: {'ya' if args.mono else 'tidak'}")
    if args.dry_run:
        print("Mode    : DRY-RUN (tidak ada file yang ditulis)")
    print("-" * 68)

    files = scan_audio_files(source_dir, result_dir)
    if not files:
        print("Tidak ada file audio yang ditemukan.")
        print(f"Ekstensi yang didukung: {', '.join(sorted(AUDIO_EXTS))}")
        return 0

    print(f"Ditemukan {len(files)} file audio.\n")

    total_src = total_out = 0
    ok_count = fail_count = 0
    current_group = None
    failed_files = []

    for src in files:
        rel = src.relative_to(source_dir)
        group = str(rel.parent) if str(rel.parent) != "." else "(root)"
        if group != current_group:
            current_group = group
            print(f"[{group}]")

        out = result_dir / rel.with_suffix(".m4a")

        if args.dry_run:
            info = probe_audio(src)
            action, kbps, reason = plan_encode(src, info, args.bitrate)
            size = (info or {}).get("size") or src.stat().st_size
            tag = "copy" if action == "copy" else f"{kbps}k"
            print(f"  {rel.name:<34} {human(size):>9}  [{tag}]  {reason}")
            total_src += size
            continue

        print(f"  {rel.name:<34} ", end="", flush=True)
        result = compress_file(src, out, args.bitrate, args.mono)

        if result is None or "error" in result:
            detail = (result or {}).get("error", "tidak diketahui")
            print(f"GAGAL - {detail}")
            failed_files.append((str(rel), detail))
            fail_count += 1
            continue

        delta = (
            (result["out_size"] - result["src_size"]) * 100.0 / result["src_size"]
            if result["src_size"] else 0.0
        )
        tag = "copy" if result["action"] == "copy" else f'{result["kbps"]}k'
        print(
            f"{human(result['src_size']):>9} -> {human(result['out_size']):>9}"
            f" {delta:>+5.0f}%  [{tag}]"
        )
        total_src += result["src_size"]
        total_out += result["out_size"]
        ok_count += 1

    print("-" * 68)

    if args.dry_run:
        print(f"{len(files)} file, total {human(total_src)}.")
        print("Jalankan tanpa --dry-run untuk mulai kompresi.")
        return 0

    # Bersihkan folder kosong yang terlanjur dibuat untuk file yang gagal.
    if result_dir.exists():
        for d in sorted(result_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()

    print(f"Selesai: {ok_count} berhasil, {fail_count} gagal.")
    if total_src:
        saved = total_src - total_out
        print(
            f"Ukuran : {human(total_src)} -> {human(total_out)}  "
            f"(hemat {human(saved)}, {saved * 100.0 / total_src:.1f}%)"
        )
    if failed_files:
        print("\nFile yang gagal:")
        for name, detail in failed_files:
            print(f"  - {name}: {detail}")
    if ok_count:
        print(f"Output  : {result_dir}")
    return 1 if fail_count else 0


if __name__ == "__main__":
    sys.exit(main())
