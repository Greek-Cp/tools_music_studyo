# Studyo Music Tools 🎵

Kumpulan script otomatisasi untuk mengelola aset suara di proyek Flutter `studyo_music_library`.

## 🚀 Fitur Utama

1.  **Auto Conversion**: Mengubah file `.wav`, `.mp3` menjadi `.m4a` (lebih ringan & optimal untuk mobile).
2.  **Auto Registration**: Otomatis mendaftarkan folder baru ke `pubspec.yaml`.
3.  **Code Generation**: Otomatis membuat `sound_enums.dart` dan `sound_paths.dart`.
4.  **Dynamic Injection**: Otomatis menambahkan Tipe Suara baru ke `bgm_manager.dart` tanpa edit manual.
5.  **Cheat Sheet**: Membuat file `quick_overview_used_new_assets.txt` berisi kode kodingan siap copas.
6.  **"NEW" Badge Tracker**: Melacak aset yang baru ditambahkan dalam 24 jam terakhir.

---

## 🛠️ Cara Penggunaan

### 1. Tambah Aset Suara

Simpan file audio Anda (format `.m4a`, `.mp3`, atau `.wav`) ke dalam folder:
`c:\Users\denis\Documents\GitHub\studyo_music_library\assets\sounds\<KATEGORI>\`

> **Tips:** Buat folder kategori baru jika perlu (misal: `assets/sounds/funny_effects/`).

### 2. Jalankan Script

Buka terminal di folder ini (`tools_music_studyo`) dan jalankan perintah utama:

```bash
python process_audio.py
```

Script ini akan melakukan semuanya secara otomatis:

1. Konversi audio (jika ada file mentah).
2. Generate kode Dart.
3. Update `pubspec.yaml` & `bgm_manager.dart`.
4. Update manifest tanggal pembuatan.

> **Catatan:** Jika Anda yakin file audio sudah aman (sudah .m4a semua) dan hanya ingin update kodingan, Anda bisa menjalankan `python generate_sound_code.py` saja untuk proses lebih cepat.

### 3. Restart Aplikasi Flutter

Setelah script selesai ("Done!"), lakukan **Full Restart** (Stop & Run ulang) pada aplikasi Flutter Anda agar perubahan terbaca.

---

## 💻 Cara Pakai di Flutter

### Melihat Aset Baru

Buka file **`quick_overview_used_new_assets.txt`** di root project.
Di sana ada daftar aset baru beserta kodenya. Tinggal **Copy Paste**!

### Contoh Manual

```dart
// Mainkan suara
await SoundController.instance.playSound(
  SoundBumpHit.hit,      // Enum nama file
  SoundType.bumpHit,     // Enum kategori (otomatis digenerate)
  onComplete: () {
    print("Suara selesai!");
  }
);
```

### Menggunakan Widget Extension

```dart
// Pada widget apapun
Container().addSound(
  SoundBumpHit.hit,
  SoundType.bumpHit,
);
```

---

## 📂 Struktur File Script

- **`process_audio.py`** (RECOMMENDED): Script utama. Mengurus konversi audio + generate kode.
- **`generate_sound_code.py`**: Hanya generate kode Dart, update Pubspec, dan Enum.
- **`fix_manifest_dates.py`**: Utility untuk reset tanggal "NEW" badge jika diperlukan.
- **`smart_fix_manifest.py`**: Utility pintar untuk mendeteksi file yang beneran baru berdasarkan tanggal file asli.

---

## ⚠️ Troubleshooting

- **Error Encoding (Windows)**: Script sudah diamankan dengan `utf-8`, jadi aman.
- **Asset Not Found**: Pastikan Anda sudah Full Restart aplikasi setelah run script.
- **SoundType Error**: Script otomatis menyuntikkan tipe baru. Jika masih merah, coba reload window VS Code atau jalankan `flutter pub get`.
