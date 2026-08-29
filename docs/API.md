# API v1.1 — Kontrak Integrasi untuk Mobile Client

> Untuk: Raihan (mobile dev). Server AI side: @drafi19.
> Base URL (dev): `http://<ip-server>:8000` — saat demo di satu WiFi, pakai IP LAN, bukan localhost.
> Docs interaktif (auto dari FastAPI): buka `http://<ip-server>:8000/docs` di browser.

## Autentikasi

Semua endpoint `/api/*` wajib mengirim header:

```
X-API-Key: <key>
```

- Key dev: minta ke sisi server (di config `api.api_key`; produksi via env `PRES_API_KEY`).
- Header hilang → `401`; key salah → `403`.
- `/health` tidak butuh key (untuk cek server hidup).

## Endpoint

### `GET /health` — cek server

```json
{"status": "ok", "model_version": "buffalo_l", "registered_users": 2}
```

### `POST /api/enroll` — daftarkan / ganti wajah user

`multipart/form-data`:

| Field  | Isi |
|--------|-----|
| `user_id` | string, id user dari sesi login app |
| `files`   | 3–10 file JPEG (foto wajah; variasi pose/pencahayaan, **bukan** foto HP layar) |

```json
// 200
{"user_id":"budi","enrolled":true,"accepted":5,"min_required":3,
 "rejected":[],"model_version":"buffalo_l","n_embeddings":5}

// 422 bila lolos < min_required (detail alasan per gambar):
{"detail":{"user_id":"cici","enrolled":false,"accepted":1,"min_required":3,
 "rejected":[{"index":2,"reason":"blurry(var=36.0)"}], ...}}
```

Alasan reject yang mungkin: `no_face`, `multiple_faces`, `face_too_small`,
`blurry(var=..)`, `too_dark(..)`, `too_bright(..)`, `spoof(p_real=..)`.
Enroll ulang user yang sama = replace (aman dipanggil ulang).

### `POST /api/verify` — presensi (verifikasi wajah, TANPA liveness)

> Endpoint ini tetap tersedia (mode sederhana), tapi **alur presensi yang
> disarankan memakai liveness** (bagian berikutnya).

`multipart/form-data`:

| Field | Isi |
|-------|-----|
| `files` | **5–10 frame JPEG** dari ±2 detik rekaman video (ambil 1 frame / ~0.3 dtk, jangan 10 frame identik) |
| `user_id` | **opsional** — id user dari sesi login. Kirim = verifikasi 1:1 (disarankan). Tidak kirim = identifikasi 1:N |

```json
// 200 — status ∈ match | no_match | spoof | no_face | low_quality
{"status":"match","user_id":"budi","confidence":0.94,
 "frames_valid":8,"frames_total":10}
```

Arti `status` & UI yang disarankan:

| status | Arti | UI |
|--------|------|-----|
| `match` | wajah cocok dgn klaim/cari | sukses, catat presensi (server juga sudah mencatat di audit log) |
| `no_match` | wajah valid tapi tidak cocok | "wajah tidak sesuai akun" |
| `spoof` | terdeteksi foto/layar, bukan orang asli | "gunakan wajah asli, bukan foto" |
| `no_face` | mayoritas frame tanpa wajah | arahkan wajah ke kamera |
| `low_quality` | frame terlalu gelap/blur/terlalu sedikit yang valid | minta pencahayaan lebih baik, ulangi |

`confidence` = median cosine similarity (match/no_match) atau mean p_real (spoof).
`user_id` non-null HANYA saat `match`.

### `GET /api/enroll/{user_id}` — info user (meta saja, tanpa biometrik)

```json
{"user_id":"budi","n_images":5,"n_embeddings":5,
 "model_version":"buffalo_l","created_at":"...","updated_at":"..."}
```

### Liveness aktif (ALUR PRESENSI YANG DISARANKAN) — kedip + senyum

Dua panggilan. Challenge dikendalikan **server** (urutan diacak per sesi —
anti-replay: rekaman video tidak bisa diputar ulang karena urutannya berubah).

**Langkah 1 — `POST /api/verify/liveness/init`**

```
multipart/form-data: user_id (opsional, dari sesi login)
```
```json
{
  "session_id": "bqb-jGyLaTnyCkslueBUAFOwyOui1X-n",
  "steps": ["smile", "blink"],            // ← urutan ACAK; ikuti ini!
  "baseline_frames": 25,
  "assumed_fps": 10.0,
  "instructions": {"neutral": "hadap kamera, ekspresi netral",
                   "blink": "KEDIP sekali", "smile": "SENYUM lebar"},
  "registered": true
}
```
App menampilkan instruksi sesuai `steps`:
1. "netral" — user diam (±2.5 dtk; kamera merekam)
2. langkah `steps[0]` (±3 dtk)
3. langkah `steps[1]` (±3 dtk)

Selama itu, app mengumpulkan frame JPEG **berurutan ±10 fps** (min **30** frame /
3 detik; maks 40).

**Langkah 2 — `POST /api/verify/liveness/{session_id}`**

```
multipart/form-data:
  files  : frame BERURUTAN dari rekaman (30..40 JPEG, ±10 fps)
  user_id: opsional (1:1); tanpa ini 1:N
```

```json
// 200 — liveness lolos + verdict
{"liveness": {"passed": true, "steps": ["smile","blink"], "missing": [],
              "blink_detected": true, "smile_detected": true},
 "status": "match", "user_id": "budi", "confidence": 0.94,
 "frames_valid": 8, "frames_total": 8}

// 409 — liveness GAGAL (challenge tak terpenuhi / video / foto)
{"detail": {"status": "liveness_fail", "passed": false,
            "steps": ["smile","blink"], "missing": ["blink","smile"],
            "blink_detected": false, "smile_detected": false}}

// 404 session tidak ada/kedaluwarsa · 409 session sudah dipakai (jangan replay!)
// 422 jumlah frame salah / terlalu sedikit frame berwajah
```

Aturan penting untuk app:

- **Session sekali pakai** — setelah complete (sukses/gagal), init lagi untuk sesi baru.
- TTL session **5 menit** — mulai challenge dekat waktu init.
- Frame **harus berurutan waktu** dari satu rekaman — jangan diacak/diambil dari galeri.
- Kedip & senyum **mengikuti `steps`** dari server, bukan urutan tetap di app.
- Setelah liveness gagal, UI: "verifikasi gagal — ulangi" → init lagi.

### `DELETE /api/enroll/{user_id}` — hapus user

`200 {"deleted":"budi"}` · `404` bila tidak ada.

### `GET /api/audit/recent?limit=50` — log verifikasi (admin/debug)

Setiap panggilan `/api/verify` tercatat server-side (ts, claimed_user,
verdict, confidence). **Record presensi resmi diturunkan dari log ini.**

## Error kode

| Kode | Arti |
|------|------|
| 401/403 | X-API-Key hilang/salah |
| 404 | user tidak terdaftar |
| 422 | payload salah: bukan gambar valid, jumlah file di luar 1..20, enroll kurang dari minimal |
| 500 | error server (laporkan + log server) |

## Catatan integrasi (penting)

1. **Kirim JPEG berkualitas ±85–90**, sisi pendek minimal ~500 px (gate wajah 112 px & gate blur sensitif resolusi — foto asli kamera aman, thumbnail tidak).
2. **Jangan kompres dua kali** (frame dari video yang sudah dikompres oke, tapi jangan resize kecil-kecil dulu).
3. Verifikasi **selalu kirim `user_id`** (1:1) — lebih cepat & akurat; 1:N hanya untuk kasus khusus.
4. Server menganggap **satu orang satu frame** — bila ada 2 wajah, frame diproses pada wajah terbesar (verifikasi) / ditolak (enroll).
5. Timeout rekomendasi client: **15 dtk** (warmup proses pertama bisa lambat; setelah itu ~0.5 dtk/frame CPU).
6. **Model_version di response**: bila berubah, semua user wajib re-enroll (server menolak galeri versi lama) — tangani pesannya di app.

## Contoh curl

```bash
KEY="dev-key-change-me"; B="http://127.0.0.1:8000"

# health
curl $B/health

# enroll
curl -X POST $B/api/enroll -H "X-API-Key: $KEY" \
  -F "user_id=budi" \
  -F "files=@f1.jpg" -F "files=@f2.jpg" -F "files=@f3.jpg"

# presensi dgn liveness (alur disarankan)
SID=$(curl -s -X POST $B/api/verify/liveness/init -H "X-API-Key: $KEY" \
  -F "user_id=budi" | sed 's/.*"session_id":"\([^"]*\)".*/\1/')
#   → app rekam mengikuti steps, lalu:
curl -X POST $B/api/verify/liveness/$SID -H "X-API-Key: $KEY" \
  -F "user_id=budi" \
  -F "files=@f001.jpg" -F "files=@f002.jpg" ... # 30-40 frame berurutan

# verifikasi tanpa liveness (mode sederhana)
curl -X POST $B/api/verify -H "X-API-Key: $KEY" \
  -F "user_id=budi" \
  -F "files=@v1.jpg" -F "files=@v2.jpg" -F "files=@v3.jpg"
```

## Belum di v1 (karena presensi resmi diturunkan dari log server, ini backlog bersama)

- Record presensi siap-pakai (check-in/check-out + jam kerja) — sekarang masih `verify_log` mentah; query analisis menyusul.
- Rate limiting per user, rotasi API key, HTTPS (butuh deployment beneran).
- WebSocket streaming (opsional; batch frame sudah cukup responsif).
