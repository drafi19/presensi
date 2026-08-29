# Panduan Pengumpulan Data (M4)

> **Audiens**: seluruh tim + sukarelawan. Tidak perlu paham kode — cukup ikuti
> perintah dan checklist di sini. Estimasi **±15 menit per orang**.
> Prinsip evaluasi: **data evaluasi ≠ data enroll** (split per SESI), dan
> serangan spoof direkam sungguhan, bukan diasumsikan.

---

## 1. Target ringkas

| Item | Minimal | Ideal |
|------|---------|-------|
| Subjek (orang) | **4** | 6–8 |
| Foto enroll per orang — sesi `s1` | **8** | 10 |
| Foto evaluasi per orang — sesi `s2` dan `s3` (beda hari) | **10 per sesi** | 12 |
| Serangan print per orang | **10** | — |
| Serangan screen per orang | **10** | — |

Kenapa begini: FAR/FRR (tingkat salah terima/salah tolak) hanya bermakna jika
diukur pada orang & kondisi yang **belum pernah** dipakai saat enroll. Itu
sebabnya `s1` dipisah dari `s2/s3`, dan dipisah per **hari**, bukan per foto.

---

## 2. Persiapan (sekali saja, di laptop server)

```bash
cd F:/R/Hermes/projects/presensi
uv sync                                             # pasang dependensi
uv run python scripts/download_models.py            # buffalo_l (~350 MB, sekali)
uv run python scripts/fetch_antispoof_weights.py    # 2 bobot anti-spoof, sekali
uv run python scripts/capture_webcam.py --list      # lihat kamera aktif
```

**Aturan emas: semua perintah python di project ini WAJIB lewat `uv run`.**
Menulis `python scripts/...` langsung = memakai Python sistem yang kosong →
`ModuleNotFoundError: No module named 'cv2'`.

**Soal kamera** (pengalaman nyata di laptop ini):

- Laptop tidak punya webcam internal aktif. Kamera eksternal USB (icspring)
  muncul sebagai `camera[1]`, sedangkan `camera[0]` ditempati driver DroidCam.
- `capture_webcam.py` punya **auto-fallback** — kalau kamera yang diminta
  gagal, dia mencari kamera hidup lain sendiri. Tapi lebih baik eksplisit:

```bash
uv run python scripts/capture_webcam.py --camera 1 --out <folder> --count <n>
```

- Layar hitam bertuliskan "Start DroidCam" = driver DroidCam nganggur, bukan
  kamera rusak. Pakai `--camera 1`, atau matikan DroidCam.

---

## 3. Struktur folder (JANGAN diubah)

```
data/raw/<subject>/<session>/*.jpg     contoh: data/raw/amin/s1/img_001.jpg
data/spoof/print/<subject>/*.jpg       serangan: wajah dicetak, difoto
data/spoof/screen/<subject>/*.jpg      serangan: wajah dari layar HP
```

- `<subject>` = nama panggilan pendek tanpa spasi (`amin`, `raihan`, `budi`).
- `<session>` = `s1` (khusus enroll), `s2`, `s3` (khusus evaluasi, beda hari).
- Foto spoof **tidak boleh** masuk `data/raw/` — mencampurnya merusak evaluasi.
- Folder `data/` di-gitignore: **foto wajah tidak pernah masuk repository**.
  Jangan pindahkan ke folder lain yang ter-track git.

---

## 4. Checklist per subjek (ikuti berurutan)

### 4.1 Enroll — sesi `s1` (±5 menit, TERPANDU OTOMATIS)

Subjek duduk ~50–70 cm dari kamera, kamera stabil (tumpu/buku). Jalankan:

```bash
uv run python scripts/guided_capture.py --mode enroll --subject <nama> --session s1 --camera 1
```

Program yang **mengarahkan**: tiap pose tampil besar di layar — **5 pose WAJIB**
(tegak → condong kiri → condong kanan → mundur → dekat; semuanya geometris,
bisa dilakukan kapan pun) + **3 pose OPSIONAL pencahayaan** (terang, samping,
remang — tekan `s` untuk lewati bila lingkungan tak memungkinkan, mis. siang
hari; variasi cahaya alami antar-hari pada s2/s3 tetap terekam). Lengkap
dengan metrik live (kelebaran wajah, kemiringan, brightness). **Foto dijepret
otomatis** saat pose tercapai & stabil (6 frame berturut-turut) dan lolos
gate penuh — termasuk anti-spoof. Gagal gate = pose diulang otomatis. Tugas
subjek cuma mengikuti arahan di layar sampai semua pose wajib selesai.

- **SPACE** = jepret manual (darurat; tetap melewati gate)
- **s** = lewati pose opsional (pencahayaan)
- **q** = keluar; lanjutkan kapan saja dengan perintah yang sama (penomoran
  file lanjut otomatis, pose yang sudah tersimpan tidak diulang)

Validasi akhir sesi (harus 100% OK karena sudah difilter saat capture):

```bash
uv run python scripts/collect_data.py --check data/raw/<nama>/s1
```

> Cadangan (mode manual per jepretan): `capture_webcam.py` — pakai bila
> lingkungan tidak memungkinkan auto-capture (mis. cahaya tak bisa diubah
> cukup untuk memenuhi kriteria pose otomatis). Foto manual WAJIB lolos
> `--check` sebelum lanjut.

### 4.3 Evaluasi — sesi `s2` dan `s3` (beda hari dengan s1)

```bash
uv run python scripts/guided_capture.py --mode eval --subject <nama> --session s2 --camera 1
uv run python scripts/collect_data.py --check data/raw/<nama>/s2
```

Mode `eval` memandu **7 pose**: 5 wajib + 2 opsional (remang ekstrem, miring
ekstrem — jadwalkan saat sesi malam bila memungkinkan). Ulangi untuk `s3` di
hari berbeda dari `s1` dan `s2`.

### 4.4 Serangan spoof (per orang: 10 + 10)

**Print** — cetak wajah subjek dari foto s1 (±15 cm); pemegang foto bergerak
mengikuti arahan jarak di layar:

```bash
uv run python scripts/guided_capture.py --mode spoof --attack print --subject <nama> --camera 1
```

**Screen** — tampilkan foto wajah full-screen di HP lain, layar menghadap kamera:

```bash
uv run python scripts/guided_capture.py --mode spoof --attack screen --subject <nama> --camera 1
```

Mode spoof memandu 10 varian (jarak sedang/dekat/jauh/miring, bergilir).
Catatan: di mode ini gate anti-spoof sengaja dilewati — label `spoof` pada
data serangan memang yang nanti diukur. Tetap divalidasi wajahnya terdeteksi:

```bash
uv run python scripts/collect_data.py --check data/spoof/print/<nama>
```

### 4.5 Rekap progres

```bash
uv run python scripts/collect_data.py --tree data/raw
uv run python scripts/collect_data.py --tree data/spoof
```

Bandingkan dengan target §1. Kirim hasil rekapnya ke tim AI (Amin) —
sisanya (evaluasi & laporan) dikerjakan dari sana.

---

## 5. Arti penolakan & cara memperbaikinya

Pesan ini muncul di `--check`, per foto:

| Alasan penolakan | Arti | Perbaikan |
|---|---|---|
| `too_dark(mean=..)` | gambar terlalu gelap (mean brightness < 40/255) | tambah lampu; jaga lampu **depan** wajah, hindari backlight jendela |
| `too_bright(mean=..)` | over-expose (mean > 240) | kurangi lampu langsung ke kamera; matikan flash |
| `blurry(var=..)` | gambar buram di mata metrik (variance Laplacian < 60) | cahaya cukup + jangan gerak saat jepret; kalau tetap, majukan jarak |
| `face_too_small` | wajah < 112 px di frame | **majukan kursi/kamera** — ini paling sering terjadi |
| `no_face` | tidak ada wajah terdeteksi | hadapkan wajah ke kamera, cek pencahayaan |
| `multiple_faces` | ada 2+ wajah (orang lain/poster di belakang) | pastikan hanya subjek di frame |
| `spoof(p_real=..)` | dicurigai foto/layar, bukan orang asli | ini wajah asli? pastikan bukan memotret layar; kalau asli & sering muncul, laporkan (data penting utk tuning) |

Catatan teknis yang perlu diketahui: deteksi blur **peka resolusi & brightness**
(variance Laplacian turun drastis pada gambar gelap atau hasil upscale). Karena
itu pencahayaan yang cukup adalah penolong #1 — setengah masalah "blurry" di
praktiknya adalah masalah cahaya.

---

## 6. Troubleshooting (kasus yang sudah pernah terjadi)

| Gejala | Penyebab | Solusi |
|---|---|---|
| `ModuleNotFoundError: No module named 'cv2'` | pakai Python sistem, bukan venv | selalu `uv run python scripts/...` |
| `GAGAL: kamera 0 tidak bisa dibuka` | index 0 ditempati DroidCam mati / kamera lain | `--list` untuk lihat index aktif; pakai `--camera 1` (tool juga auto-fallback) |
| Layar "Start DroidCam" hitam di preview | driver DroidCam belum distart | pakai `--camera 1`, atau start DroidCam bila memang mau pakai HP |
| Crash `Assertion failed _step >= minstep` saat capture | versi lama script (resolusi diganti di tengah stream) | sudah diperbaiki (`3f8ff1b`) — `git pull` dulu sebelum sesi |
| Banyak `face_too_small` | jarak terlalu jauh utk 640×480–720p | majukan; target wajah mengisi ≥ 1/3 tinggi frame |
| Foto di HP lebih tajam? | boleh | boleh, asal **konsisten per sesi** (jangan campur webcam & HP dalam satu sesi) |

Sebelum sesi: `git pull` untuk ambil versi tool terbaru.

---

## 7. Etika & keamanan data

- Semua subjek tahu wajahnya dipakai evaluasi sistem presensi; boleh mundur
  kapan saja tanpa alasan.
- Foto wajah = data biometrik. Semua hidup di `data/` (gitignored) di laptop
  server. **Jangan upload ke cloud/drive publik, jangan kirim via chat.**
- Yang dibagikan antar tim hanya angka & metrik agregat (output evaluasi),
  bukan gambar.
- Nama folder pakai nama panggilan, bukan nama lengkap/NIM.

---

## 8. Setelah data lengkap — serahkan ke tim AI

```bash
# Identifikasi 1:1 — kurva FAR/FRR + threshold @ target FAR 1%
uv run python scripts/eval_pairs.py --raw data/raw --target-far 0.01
uv run python scripts/eval_pairs.py --raw data/raw --target-far 0.01 --apply   # tulis ke config

# Anti-spoof — TPR/TNR/FPR
uv run python scripts/eval_antispoof.py --spoof data/spoof --raw data/raw

# Simulasi mode app: video rekaman -> frame -> verdict
uv run python scripts/extract_frames.py --video rekaman.mp4 --out data/frames
uv run python scripts/verify_cli.py --user <nama> --images data/frames/*.jpg
```

Hasil akhir dicatat di `docs/eval/REPORT.md` (kurva FAR/FRR, EER, keputusan
threshold, metrik anti-spoof, keterbatasan) — bagian penutup portofolio.

---

*Riwayat singkat tool: `capture_webcam.py` direvisi setelah crash MSMF nyata
(resolusi kini diset sebelum frame pertama + auto-reopen); `--check` menerima
folder maupun satu file; `collect_data.py --tree` tidak memuat model (cepat).*
