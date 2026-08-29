# Protokol Pengumpulan Data (M4)

> Tujuan: evaluasi yang bisa dibela — bukan sekadar "jalan". Prinsip:
> **data evaluasi ≠ data enroll** (split per SESI, bukan per foto), dan
> serangan spoof direkam sungguhan, bukan diasumsikan.

## 0. Etika & kebersihan data

- Semua subjek adalah sukarelawan yang tahu wajahnya dipakai untuk evaluasi
  sistem presensi (mereka boleh mundur kapan saja).
- Foto wajah = data biometrik. **Semua berada di `data/` yang di-gitignore** —
  yang di-commit hanya metrik agregat (angka similarity, bukan gambar).
- Simpan di mesin lokal; jangan upload galeri/foto ke cloud publik.

## 1. Struktur folder

```
data/raw/<subject>/<session>/*.jpg     contoh: data/raw/rafi/s1/img_001.jpg
data/spoof/print/*.jpg                 serangan: wajah dicetak, difoto
data/spoof/screen/*.jpg                serangan: wajah dari layar HP
```

- `<subject>`: nama panggilan pendek (bukan nama lengkap/NIM).
- `<session>`: `s1`, `s2`, `s3` — **sesi beda waktu/hari/outfit**.
  - `s1` = khusus ENROLL (tidak dipakai evaluasi).
  - `s2`, `s3` = EVALUASI (tidak boleh dipakai enroll).

## 2. Jumlah minimal layak evaluasi

| Item | Minimal | Catatan |
|------|---------|---------|
| Subjek | 4 orang | di bawah itu FAR/FRR tidak bermakna; ideal 6–8 |
| Foto enroll per orang (s1) | 8 | variasi: tegak/miring ±15°, dekat/jauh, 2 level cahaya |
| Foto eval per orang (s2, s3) | 10 per sesi | kondisi sama seperti s1 + 1 kondisi "sulit" (remang) |
| Serangan print | 10 per orang | foto wajah dicetak (kertas), difoto HP |
| Serangan screen | 10 per orang | foto ditampilkan di layar HP, layar difoto |

## 3. Prosedur foto (per subjek)

0. Pilih kamera dulu: `uv run python scripts/capture_webcam.py --list`
   (webcam USB biasanya `camera[1]` bila DroidCam menempati index 0; tool
   punya auto-fallback bila index salah).
1. Kamera laptop/HP pegangan tetap; subjek ~50–70 cm dari kamera.
2. Sesi s1: ambil 8 foto mengikuti checklist: tegak, miring kiri, miring
   kanan, mundur 1 langkah, dekat, cahaya depan, cahaya samping, remang ringan.
3. Sesi s2/s3 (minimal beda hari): ulangi pola yang sama; tambah 2 foto
   "sulit" (remang lebih kuat / pose ekstrem ringan).
4. Jalankan validasi on-the-spot (§4) — foto yang ditolak diulang sebelum
   sesi selesai, biar tidak bolak-balik.

## 4. Validasi on-the-spot

```bash
uv run python scripts/collect_data.py --check data/raw/rafi/s1
```

Menampilkan per foto: `OK` / ditolak + alasan (`no_face`, `blurry`,
`face_too_small`, `spoof`). Ulangi foto yang ditolak.

## 5. Prosedur serangan spoof

- Print: cetak wajah subjek ukuran wajah nyata (±15 cm), pegang di depan
  kamera, foto seperti presensi biasa (10×/orang, variasi jarak).
- Screen: tampilkan foto wajah full-screen di HP lain, arahkan ke kamera (10×/orang).
- JANGAN pernah masukkan file ini ke folder `raw/` (mencampur attack dengan
  bona fide merusak evaluasi).

## 6. Setelah data lengkap — eksekusi evaluasi

```bash
# 1. Identifikasi 1:1 — kurva FAR/FRR + rekomendasi threshold @ FAR 1%
uv run python scripts/eval_pairs.py --raw data/raw --target-far 0.01

# lihat hasilnya, bila mau diterapkan ke config (tercatat eksplisit):
uv run python scripts/eval_pairs.py --raw data/raw --target-far 0.01 --apply

# 2. Anti-spoof — TPR/TNR/FPR pada threshold saat ini
uv run python scripts/eval_antispoof.py --spoof data/spoof --raw data/raw

# 3. Verifikasi mode app: video -> frame batch -> verdict
uv run python scripts/extract_frames.py --video rekaman_presensi.mp4 --out data/test/frames
uv run python scripts/verify_cli.py --user rafi --images data/test/frames/*.jpg
```

Hasil evaluasi (angka + keputusan threshold) dicatat ke `docs/eval/REPORT.md`
— bagian paling penting dari portofolio ini.
