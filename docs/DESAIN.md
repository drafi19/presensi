# Desain Teknis — Aplikasi Presensi Face Recognition

> Status: DRAFT v1 untuk didiskusikan · Fokus: komponen AI · Mobile dev: Raihan
> Tujuan project: **portofolio** → deliverable bukan cuma "app jalan", tapi arsitektur rapi + evaluasi terukur yang bisa dibela saat ditanya.

---

## 1. Ringkasan

Sistem presensi dengan verifikasi wajah. HP mengambil video realtime, server Python melakukan
deteksi wajah → anti-spoofing → ekstraksi embedding → matching terhadap user terdaftar.

```
┌─────────────┐   frame JPEG (batch)   ┌──────────────────────────────┐
│  Mobile App │ ─────────────────────▶ │  API Server (Python/FastAPI) │
│   (Raihan)  │ ◀───────────────────── │  ┌────────┐  ┌────────────┐  │
└─────────────┘   verdict JSON         │  │ Detect │─▶│ Anti-Spoof │  │
                                       │  └────────┘  └─────┬──────┘  │
                                       │                    ▼         │
                                       │              ┌────────────┐  │
                                       │   gallery ◀──│  Embedding │  │
                                       │   (npz/sqlite)│  (ArcFace) │  │
                                       │              └─────┬──────┘  │
                                       │                    ▼         │
                                       │              ┌────────────┐  │
                                       │              │   Match    │  │
                                       │              │  + voting  │  │
                                       │              └────────────┘  │
                                       └──────────────────────────────┘
```

### Alur end-to-end (multi-user; app terpasang di HP tiap user)

1. User download app + login (Raihan) — akun mengikat HP ke identitas `user_id`.
2. App memvalidasi user berada di area kerja (GPS/geofence) — **domain Raihan**; server AI tidak ikut memvalidasi lokasi. Catatan kejujuran untuk Q&A: GPS client-side bisa dipalsukan (mock location) — cukup untuk scope v1, disebut sebagai keterbatasan.
3. App merekam ±2 detik, mengirim batch frame **+ `user_id` dari sesi login**.
4. Server melakukan verifikasi wajah (pipeline §3) dan memutuskan.
5. `match` → presensi tercatat: server menulis **audit log** tiap hasil verify (user_id, verdict, confidence, timestamp); record presensi + aturan bisnis (jam kerja, check-in/out) dibagi dengan Raihan (lihat §7).

## 2. Keputusan Teknis (dengan alternatif yang ditolak)

| # | Keputusan | Alternatif | Alasan |
|---|-----------|------------|--------|
| 1 | Model **server-side** (API Python) | On-device TFLite | Development & tuning jauh lebih cepat; update model tidak perlu update app. On-device = future work. |
| 2 | Embedding: **ArcFace via InsightFace (buffalo_l)** | FaceNet (facenet-pytorch), training dari nol | ArcFace = standar industri, pretrained kuat, pipeline detect+align+embed satu paket (SCRFD). Training dari nol butuh data wajah jutaan — tidak realistis dan tidak perlu. Nilai kerja kita ada di **pipeline, threshold, dan evaluasi**, bukan melatih backbone. |
| 3 | Anti-spoofing: **MiniFASNet (Silent-Face-Anti-Spoofing)** — model, bukan challenge interaktif | Liveness interaktif (kedip/putar kepala), tekstur analisis | Sesuai pilihan: model-based, 1 frame cukup, ringan (~10 MB), MIT license. User tidak perlu gerakan khusus → UX presensi cepat. |
| 4 | Verifikasi: **batch frame** (app rekam ±2 dtk, sample 5–10 frame, kirim 1 request) | WebSocket streaming | Tanpa state server & tanpa kompleksitas WS untuk v1; latensi tetap <1–2 dtk. WS jadi upgrade kalau Raihan mau overlay feedback live. |
| 5 | Matching: **cosine similarity brute-force (numpy)** | Vector DB (FAISS, Milvus) | Skala presensi = puluhan–ratusan orang; numpy linear scan <1 ms. FAISS overkill — tidak ada cerita di portofolio untuk itu. |
| 6 | Storage: **SQLite + file .npz** (gallery embeddings) | PostgreSQL, cloud | Zero-infra, cukup, gampang dibackup. |
| 7 | Runtime: **onnxruntime CPU** | GPU/CUDA | buffalo_l ≈ 100–200 ms/frame CPU, MiniFASNet <50 ms → batch 8 frame ±1.5 s. Cukup untuk v1. GPU opsional belakangan. |

## 3. Pipeline (per frame)

1. **Quality gate** — blur (variance Laplacian) + ukuran wajah minimum + brightness. Frame jelek dibuang sebelum proses berat.
2. **Detection** — SCRFD (bagian InsightFace). >1 wajah = tolak (cegah presensi patungan); 0 wajah = tolak.
3. **Alignment** — landmark 5 titik → similarity transform ke 112×112.
4. **Anti-spoofing** — MiniFASNet pada crop wajah → label {real, spoof} + skor. Spoof → frame gugur, masuk voting.
5. **Embedding** — ArcFace (w600k_r50) → vektor 512-d, dinormalisasi L2.
6. **Matching** — cosine similarity vs gallery; ambil skor tertinggi; bandingkan **threshold global** (di-tune dari evaluasi, bukan angka hoki).

## 4. Voting antar-frame (agregasi verifikasi)

Dari N frame valid (lolos quality + anti-spoof), ambil **median similarity** per kandidat (lebih robust daripada mean terhadap frame outlier), lalu:

- `match`    : median sim ≥ threshold DAN ≥ 70% frame valid sepakat user sama
- `no_match` : frame valid cukup, tapi skor di bawah threshold
- `spoof`    : ≥ 70% frame terdeteksi spoof
- `no_face` / `low_quality` : gagal kualitas dominan

Error case ini adalah **kontrak dengan Raihan** — app harus punya UI untuk masing-masing.

## 5. Enrollmen (pendaftaran wajah)

- 5–10 foto per orang: variasi pose kecil, jarak, pencahayaan (bukan 10 foto identik).
- Tiap gambar enroll **dilewati quality gate + anti-spoof juga** — mencegah galeri tercemar foto HP.
- Simpan: `user_id → [embedding per gambar]` + metadata (timestamp, versi model).
- Versi model tercatat: kalau ganti backbone, gallery lama **wajib re-enroll** (embedding antar-model tidak comparable) → jadi field `model_version` di DB.
- Multi-user: enroll sekali per user — lewat app (self-enroll terpandu setelah login) atau dibantu admin. Endpoint sama; yang membedakan siapa yang memanggil.

## 6. Evaluasi (bagian yang menjual di portofolio)

**Yang diukur, bukan diklaim:**

| Eksperimen | Data | Output |
|---|---|---|
| Identifikasi 1:1 | pasangan genuine/imposter dari anggota tim + sukarelawan (tiap orang ±10 sesi) | kurva FAR–FRR, pilih threshold di target operasional (mis. FAR ≤ 1%) → laporkan FRR-nya |
| Anti-spoofing | self-collected: cetak foto + replay layar HP (attack), wajah asli (bona fide) | TPR/TNR + FPR @ skor tertentu; protokol dijelaskan di README |
| Robustness pencahayaan | variasi siang/malam/indoor | degradasi akurasi dilaporkan apa adanya |

- **PENTING (disiplin metodologi):** data evaluasi TIDAK boleh sama dengan data enroll (train/test separation). Split per sesi, bukan per foto.
- Threshold final dikunci dari eksperimen, ditulis di config, tidak diubah-ubah manual.
- Jujur di README: pretrained ArcFace dilatih di wajah web (domain gap mungkin dengan kondisi kamera HP indoor); MiniFASNet pretrained mungkin perlu fine-tune untuk tipe serangan lokal. Laporkan batasnya.

## 7. API Contract (v1, untuk Raihan)

Base: `http://<server>:8000` · Format: JSON · Error = HTTP 4xx/5xx + `{"detail": "..."}`

### `POST /api/enroll`
```
multipart/form-data:
  user_id: string
  images : file[] (5–10 JPEG)
→ 200 {"user_id": "...", "n_faces_enrolled": 7, "model_version": "buffalo_l",
       "rejected": [{"index": 2, "reason": "low_quality"}]}
→ 422 kalau <3 gambar lolos
```

### `POST /api/verify`
```
multipart/form-data:
  frames: file[] (5–10 JPEG dari ±2 detik rekaman)
  user_id: string (opsional — dari sesi login)
→ 200 {
  "status": "match" | "no_match" | "spoof" | "no_face" | "low_quality",
  "user_id": "budi" | null,
  "confidence": 0.87,          // median similarity (match) atau spoof-score
  "frames_valid": 6, "frames_total": 8,
  "model_version": "buffalo_l"
}
```

### Aturan yang perlu disepakati dengan Raihan
- **Dua mode verify**: kalau `user_id` dikirim → **verifikasi 1:1** (server cek "apakah ini benar wajah user X?" — mode default yang disarankan: binding akun eksplisit, lebih cepat). Kalau tidak dikirim → **identifikasi 1:N** (server mencari siapa orangnya di gallery; butuh margin top-1 vs top-2). Rekomendasi: 1:1, karena app sudah punya login.
- Frame dikirim **sebagai JPEG** (quality ±85), resolusi bebas tapi wajah ≥ ~112 px.
- App **tidak melakukan matching lokal** — semua keputusan dari server.
- `status` selalu ada; `user_id` hanya non-null saat `match`.
- `DELETE /api/enroll/{user_id}` untuk hapus, `GET /api/enroll/{user_id}` cek terdaftar.
- **Audit log**: server mencatat setiap panggilan verify (user_id, verdict, confidence, timestamp). Record presensi resmi **diturunkan dari log server, bukan klaim app** — app tidak bisa bilang "match" tanpa bukti server.
- **Auth minimal v1**: header `X-API-Key` statik — terutama melindungi `/enroll` agar tidak sembarang orang mendaftarkan wajah.
- **GPS/geofence = domain app (Raihan)**. Server menerima (opsional) koordinat sebagai metadata yang di-log; tidak ikut memvalidasi lokasi.

## 8. Struktur Repo

```
presensi/
├── IDEA.md, README.md
├── docs/DESAIN.md          ← dokumen ini
├── config.yaml             ← threshold, parameter, model_version (single source of truth)
├── src/presensi/
│   ├── api/                (FastAPI routes, schemas)
│   ├── pipeline/           (detect, align, antispoof, embed, match, voting)
│   ├── storage/            (gallery sqlite/npz)
│   └── quality/            (blur, brightness, size gates)
├── scripts/                (enroll_cli.py, eval_pairs.py, tune_threshold.py, collect_data.py)
├── tests/                  (unit: voting, threshold logic; integration: pipeline end-to-end)
└── data/                   (gitignored: gallery, eval sets)
```

## 9. Roadmap

| Tahap | Isi | Selesai jika |
|---|---|---|
| M1 | Skeleton repo + environment + insightface & anti-spoof jalan di script lokal | satu foto → embedding + verdict spoof/real, tercetak |
| M2 | Pipeline lengkap + storage gallery + CLI enroll/verify | enroll 2 orang, verify benar & salah konsisten |
| M3 | API FastAPI + contract final + audit log verify + X-API-Key + contoh curl/Postman | Raihan bisa integrate tanpa tanya kode kita |
| M4 | Kumpul data + evaluasi + tuning threshold + README metrik | tabel FAR/FRR + keputusan threshold terdokumentasi |
| M5 (opsional) | WebSocket live, fine-tune anti-spoof, logging presensi + jadwal | — |

**Paralel dengan Raihan**: begitu kontrak API (§7) disepakati, dia bisa kerja UI + network layer pakai server mock, tidak perlu menunggu model.

## 10. Risiko & Mitigasi

| Risiko | Mitigasi |
|---|---|
| Presensi dibohongi foto HP teman | Anti-spoof di frame verifikasi **dan** enroll; voting multi-frame |
| InsightFace install ribet di Windows (onnxruntime) | venv khusus project, onnxruntime CPU wheel resmi ada untuk Windows |
| Domain gap pretrained model | Evaluasi dengan data kondisi nyata (§6); threshold dari data sendiri |
| Latency lambat di server lemah | Quality gate membuang frame sebelum proses; batch kecil; GPU opsional |
